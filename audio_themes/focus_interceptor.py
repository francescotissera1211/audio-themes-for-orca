"""Monkey-patches for Orca's focus and mode-change systems.

Intercepts focus changes to play role-appropriate sounds, and intercepts
mode transitions to play focus/browse mode sounds.  All patches are
reversible via uninstall().
"""

from __future__ import annotations

import logging
import os

import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib

from orca import focus_manager, document_presenter, command_manager, keybindings
from orca import speech_generator
from orca.scripts.web import speech_generator as web_speech_generator
from orca.ax_object import AXObject
from orca.ax_utilities import AXUtilities

from .config import Config, THEMES_DIR
from .role_map import ROLE_TO_SOUND, MODE_SOUNDS
from .sound_player import get_player, get_overlay_player, get_screen_size

_log = logging.getLogger("orca-audio-themes")

# Module state
_config: Config | None = None
_installed: bool = False
_sound_played_for_focus: bool = False  # True when a theme sound was just played

# Original methods (saved for uninstall)
_orig_set_locus: object = None
_orig_set_presentation_mode: object = None
_orig_enable_sticky_focus: object = None
_orig_enable_sticky_browse: object = None
_orig_generate_accessible_role: object = None
_orig_web_generate_accessible_role: object = None
_orig_set_active_window: object = None


# ---------------------------------------------------------------------------
# Position helpers
# ---------------------------------------------------------------------------

def _get_screen_position(obj: Atspi.Accessible) -> tuple[int, int]:
    """Return (centre_x, centre_y) of obj in screen coordinates, or (-1, -1)."""
    if not AXObject.supports_component(obj):
        return -1, -1
    try:
        rect = Atspi.Component.get_extents(obj, Atspi.CoordType.SCREEN)
    except Exception:
        return -1, -1
    if rect is None or rect.width <= 0:
        return -1, -1
    cx = rect.x + rect.width // 2
    cy = rect.y + rect.height // 2
    return cx, cy


def _compute_position(obj: Atspi.Accessible) -> tuple[float, float]:
    """Compute (pan, elevation) from obj's screen position.

    pan: -1.0 (left) to 1.0 (right)
    elevation: -1.0 (bottom) to 1.0 (top)
    """
    cx, cy = _get_screen_position(obj)
    if cx < 0:
        return 0.0, 0.0

    sw, sh = get_screen_size()
    if sw <= 0 or sh <= 0:
        return 0.0, 0.0

    pan = max(-1.0, min(1.0, (2.0 * cx / sw) - 1.0))
    # Y axis is inverted: 0=top of screen, sh=bottom
    elevation = max(-1.0, min(1.0, 1.0 - (2.0 * cy / sh)))
    return pan, elevation


# ---------------------------------------------------------------------------
# Sound file resolution (with default theme fallback)
# ---------------------------------------------------------------------------

def _resolve_sound_path(sound_file: str) -> str | None:
    """Return the path to a sound file, falling back to the default theme."""
    if _config is None:
        return None
    # Try active theme first
    theme_dir = _config.theme_dir
    if theme_dir:
        path = os.path.join(theme_dir, sound_file)
        if os.path.isfile(path):
            return path
    # Fall back to default theme
    default_path = os.path.join(THEMES_DIR, "default", sound_file)
    if os.path.isfile(default_path):
        return default_path
    return None


# ---------------------------------------------------------------------------
# Special property detection
# ---------------------------------------------------------------------------

_CONTAINER_ROLES = frozenset([
    Atspi.Role.LIST,
    Atspi.Role.LIST_BOX,
    Atspi.Role.TREE,
    Atspi.Role.TREE_TABLE,
    Atspi.Role.COMBO_BOX,
    Atspi.Role.MENU,
    Atspi.Role.PAGE_TAB_LIST,
])


def _find_container_and_index(obj: Atspi.Accessible) -> tuple[Atspi.Accessible | None, int]:
    """Walk up from obj to find the nearest list/tree container and the child index within it.

    Returns (container, index) or (None, -1).
    """
    current = obj
    for _ in range(10):  # don't walk too far
        parent = AXObject.get_parent(current)
        if parent is None:
            return None, -1
        try:
            parent_role = AXObject.get_role(parent)
        except Exception:
            return None, -1
        if parent_role in _CONTAINER_ROLES:
            idx = AXObject.get_index_in_parent(current)
            return parent, idx
        current = parent
    return None, -1


def _check_first_last(obj: Atspi.Accessible) -> str | None:
    """Return 'first_item.wav' or 'last_item.wav' if obj is first/last in a container."""
    try:
        container, index = _find_container_and_index(obj)
        if container is None or index < 0:
            return None
        n_children = AXObject.get_child_count(container)
        if n_children <= 1:
            return None
        if index == 0:
            return "first_item.wav"
        if index == n_children - 1:
            return "last_item.wav"
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Focus change hook
# ---------------------------------------------------------------------------

def _patched_set_locus_of_focus(self, event, obj, notify_script=True, force=False):
    """Wrapper around FocusManager.set_locus_of_focus that plays theme sounds."""
    global _sound_played_for_focus
    _sound_played_for_focus = False

    old_focus = self._focus

    # Play the sound BEFORE the original method so that the flag is set
    # when Orca's speech generator runs (which happens inside the original).
    if _config is not None and _config.enabled and _config.play_on_focus:
        # Peek at what the new focus will be (obj), but note the original
        # method may reject it.  We accept this minor race for simplicity.
        if obj is not None and obj != old_focus:
            try:
                role = AXObject.get_role(obj)
            except Exception:
                role = None

            sound_file = ROLE_TO_SOUND.get(role) if role is not None else None
            if sound_file is not None and sound_file not in _config.disabled_sounds:
                if _config.positional_audio:
                    pan, elevation = _compute_position(obj)
                else:
                    pan, elevation = 0.0, 0.0

                # For item roles, try to play first/last cue instead
                _ITEM_SOUNDS = ("list_item.wav", "tree_item.wav", "table_cell.wav")
                played_first_last = False
                if sound_file in _ITEM_SOUNDS:
                    first_last = _check_first_last(obj)
                    if first_last and first_last not in _config.disabled_sounds:
                        cue_path = _resolve_sound_path(first_last)
                        if cue_path:
                            get_player().play(
                                cue_path, pan=pan, elevation=elevation,
                                volume=_config.volume,
                            )
                            _sound_played_for_focus = True
                            played_first_last = True

                # Play the role sound if first/last didn't replace it
                if not played_first_last:
                    path = _resolve_sound_path(sound_file)
                    if path:
                        get_player().play(path, pan=pan, elevation=elevation,
                                          volume=_config.volume)
                        _sound_played_for_focus = True

    _orig_set_locus(self, event, obj, notify_script, force)


# ---------------------------------------------------------------------------
# Role speech suppression
# ---------------------------------------------------------------------------

# Roles whose speech should NOT be suppressed even when speak_roles is off,
# because Orca adds useful context (e.g. "list with 11 items", "leaving list").
_ALWAYS_SPEAK_ROLES = frozenset([
    Atspi.Role.LIST,
    Atspi.Role.LIST_BOX,
    Atspi.Role.TREE,
    Atspi.Role.TREE_TABLE,
    Atspi.Role.TABLE,
    Atspi.Role.MENU,
    Atspi.Role.MENU_BAR,
])


def _should_suppress_role(obj: Atspi.Accessible, is_web: bool = False) -> bool:
    """Check if role speech should be suppressed right now."""
    global _sound_played_for_focus
    if _sound_played_for_focus and _config is not None and not _config.speak_roles:
        # In web content, let container roles speak (e.g. "list with 11 items")
        if is_web:
            try:
                role = AXObject.get_role(obj)
            except Exception:
                role = None
            if role in _ALWAYS_SPEAK_ROLES:
                return False
        _sound_played_for_focus = False
        return True
    return False


def _patched_generate_accessible_role(self, obj, **args):
    """Suppress role speech when a theme sound just played and speak_roles is off."""
    if _should_suppress_role(obj, is_web=False):
        return []
    return _orig_generate_accessible_role(self, obj, **args)


def _patched_web_generate_accessible_role(self, obj, **args):
    """Same suppression for the web script's speech generator."""
    if _should_suppress_role(obj, is_web=True):
        return []
    return _orig_web_generate_accessible_role(self, obj, **args)


# ---------------------------------------------------------------------------
# Window change hook
# ---------------------------------------------------------------------------

def _patched_set_active_window(self, frame, app=None, set_window_as_focus=False,
                               notify_script=False):
    """Wrapper around FocusManager.set_active_window that plays a sound."""
    global _sound_played_for_focus
    old_window = self._window
    is_new_window = frame is not None and frame != old_window

    # Play sound and set flag BEFORE original so "Frame" speech is suppressed.
    # Skip transient popups (combo box dropdowns, popup menus, tooltips).
    if is_new_window and _config is not None and _config.enabled:
        skip = (
            AXUtilities.is_combo_box_popup(frame)
            or AXUtilities.is_popup_menu(frame)
            or AXUtilities.is_tool_tip(frame)
        )
        if not skip:
            sound_file = MODE_SOUNDS.get("window_activate")
            if sound_file and sound_file not in _config.disabled_sounds:
                path = _resolve_sound_path(sound_file)
                if path:
                    get_overlay_player().play(path, volume=_config.volume)
                    _sound_played_for_focus = True

    _orig_set_active_window(self, frame, app, set_window_as_focus, notify_script)


# ---------------------------------------------------------------------------
# Mode change hooks
# ---------------------------------------------------------------------------

def _should_suppress_mode_speech() -> bool:
    """True when mode-change speech should be suppressed (sound replaces it)."""
    return (
        _config is not None
        and _config.enabled
        and _config.play_on_mode_change
        and not _config.speak_roles
    )


def _mute_present_message(func):
    """Temporarily replace present_message with a no-op, then restore."""
    from orca import presentation_manager

    class _Ctx:
        def __enter__(self_ctx):
            mgr = presentation_manager.get_manager()
            self_ctx._orig = mgr.present_message
            mgr.present_message = lambda *a, **kw: None
            return self_ctx

        def __exit__(self_ctx, *exc):
            presentation_manager.get_manager().present_message = self_ctx._orig

    return _Ctx()


def _play_mode_sound(mode_key: str) -> None:
    """Play a mode-change sound if enabled."""
    if _config is None or not _config.enabled or not _config.play_on_mode_change:
        return
    sound_file = MODE_SOUNDS.get(mode_key)
    if sound_file is None or sound_file in _config.disabled_sounds:
        return
    path = _resolve_sound_path(sound_file)
    if path:
        # Use overlay player so mode sounds don't interrupt role sounds
        get_overlay_player().play(path, volume=_config.volume)


def _patched_set_presentation_mode(self, script, use_focus_mode, obj=None,
                                   document=None, notify_user=True):
    """Wrapper around DocumentPresenter._set_presentation_mode."""
    if _should_suppress_mode_speech():
        with _mute_present_message(None):
            result = _orig_set_presentation_mode(
                self, script, use_focus_mode, obj, document, notify_user,
            )
    else:
        result = _orig_set_presentation_mode(
            self, script, use_focus_mode, obj, document, notify_user,
        )

    if result:
        if use_focus_mode:
            _play_mode_sound("focus_mode")
        else:
            _play_mode_sound("browse_mode")

    return result


def _patched_enable_sticky_focus(self, script, event=None, notify_user=True):
    """Wrapper around DocumentPresenter.enable_sticky_focus_mode."""
    if _should_suppress_mode_speech():
        with _mute_present_message(None):
            result = _orig_enable_sticky_focus(self, script, event, notify_user)
    else:
        result = _orig_enable_sticky_focus(self, script, event, notify_user)
    _play_mode_sound("focus_mode_sticky")
    return result


def _patched_enable_sticky_browse(self, script, event=None, notify_user=True):
    """Wrapper around DocumentPresenter.enable_sticky_browse_mode."""
    if _should_suppress_mode_speech():
        with _mute_present_message(None):
            result = _orig_enable_sticky_browse(self, script, event, notify_user)
    else:
        result = _orig_enable_sticky_browse(self, script, event, notify_user)
    _play_mode_sound("browse_mode_sticky")
    return result


# ---------------------------------------------------------------------------
# Settings GUI keybinding
# ---------------------------------------------------------------------------

_keybinding_registered = False


def _open_settings(script, event=None):
    """Keybinding handler for Orca+Ctrl+A."""
    GLib.idle_add(_show_settings_ui)
    return True


def _show_settings_ui() -> bool:
    """Open the settings dialog on the main thread."""
    global _config
    try:
        from .config_ui import show_settings_dialog
        show_settings_dialog(_config, on_save=_on_settings_saved)
    except Exception as e:
        _log.error("AudioThemes: could not open settings: %s", e, exc_info=True)
        try:
            from orca import presentation_manager
            presentation_manager.get_manager().present_message(
                f"Error opening Audio Themes settings: {e}"
            )
        except Exception:
            pass
    return False


def _on_settings_saved(config: Config) -> None:
    """Callback when settings are saved from the UI."""
    global _config
    _config = config


def _register_keybinding() -> bool:
    """Register Orca+Ctrl+A for the settings dialog."""
    global _keybinding_registered
    if _keybinding_registered:
        return False
    try:
        manager = command_manager.get_manager()
        kb = keybindings.KeyBinding("a", keybindings.ORCA_CTRL_MODIFIER_MASK)
        manager.add_command(
            command_manager.KeyboardCommand(
                name="audioThemesSettings",
                function=_open_settings,
                group_label="Audio Themes",
                description="Open Audio Themes settings",
                desktop_keybinding=kb,
                laptop_keybinding=kb,
            )
        )
        _keybinding_registered = True
        _log.info("AudioThemes: keybinding Orca+Ctrl+A registered")
    except Exception as e:
        _log.error("AudioThemes: failed to register keybinding: %s", e)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install() -> None:
    """Apply all monkey-patches and register keybinding. Called from orca-customizations.py."""
    global _config, _installed
    global _orig_set_locus, _orig_set_presentation_mode
    global _orig_enable_sticky_focus, _orig_enable_sticky_browse
    global _orig_generate_accessible_role, _orig_web_generate_accessible_role
    global _orig_set_active_window

    if _installed:
        return

    _config = Config.load()

    # Patch focus changes
    _orig_set_locus = focus_manager.FocusManager.set_locus_of_focus
    focus_manager.FocusManager.set_locus_of_focus = _patched_set_locus_of_focus

    # Patch role speech suppression (base + web subclass)
    _orig_generate_accessible_role = speech_generator.SpeechGenerator._generate_accessible_role
    speech_generator.SpeechGenerator._generate_accessible_role = _patched_generate_accessible_role

    _orig_web_generate_accessible_role = web_speech_generator.SpeechGenerator._generate_accessible_role
    web_speech_generator.SpeechGenerator._generate_accessible_role = _patched_web_generate_accessible_role

    # Patch window changes
    _orig_set_active_window = focus_manager.FocusManager.set_active_window
    focus_manager.FocusManager.set_active_window = _patched_set_active_window

    # Patch mode transitions
    _orig_set_presentation_mode = document_presenter.DocumentPresenter._set_presentation_mode
    document_presenter.DocumentPresenter._set_presentation_mode = _patched_set_presentation_mode

    _orig_enable_sticky_focus = document_presenter.DocumentPresenter.enable_sticky_focus_mode
    document_presenter.DocumentPresenter.enable_sticky_focus_mode = _patched_enable_sticky_focus

    _orig_enable_sticky_browse = document_presenter.DocumentPresenter.enable_sticky_browse_mode
    document_presenter.DocumentPresenter.enable_sticky_browse_mode = _patched_enable_sticky_browse

    # Register keybinding on the main thread
    GLib.idle_add(_register_keybinding)

    _installed = True
    _log.info(
        "AudioThemes: installed (enabled=%s, theme=%s, positional=%s)",
        _config.enabled, _config.active_theme, _config.positional_audio,
    )


def uninstall() -> None:
    """Remove all monkey-patches and restore originals."""
    global _installed

    if not _installed:
        return

    if _orig_set_locus is not None:
        focus_manager.FocusManager.set_locus_of_focus = _orig_set_locus
    if _orig_set_active_window is not None:
        focus_manager.FocusManager.set_active_window = _orig_set_active_window
    if _orig_generate_accessible_role is not None:
        speech_generator.SpeechGenerator._generate_accessible_role = _orig_generate_accessible_role
    if _orig_web_generate_accessible_role is not None:
        web_speech_generator.SpeechGenerator._generate_accessible_role = _orig_web_generate_accessible_role
    if _orig_set_presentation_mode is not None:
        document_presenter.DocumentPresenter._set_presentation_mode = _orig_set_presentation_mode
    if _orig_enable_sticky_focus is not None:
        document_presenter.DocumentPresenter.enable_sticky_focus_mode = _orig_enable_sticky_focus
    if _orig_enable_sticky_browse is not None:
        document_presenter.DocumentPresenter.enable_sticky_browse_mode = _orig_enable_sticky_browse

    get_player().shutdown()
    get_overlay_player().shutdown()
    _installed = False
    _log.info("AudioThemes: uninstalled")
