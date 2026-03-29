"""Accessible GTK3 settings dialog for Orca Audio Themes.

Two-page layout (sidebar + Gtk.Stack):
  - General: master enable, theme selection, volume, positional audio, etc.
  - Theme Editor: per-role sound assignment with preview/change/reset.

Follows the same AT-SPI event suspension and FocusManagedListBox patterns
as Polyglot and Clock for Orca.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Atk", "1.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Atk, Gdk, GLib

from .config import Config, THEMES_DIR
from .role_map import ALL_SOUND_FILES, SOUND_LABELS, NVDA_ID_TO_FILENAME

_log = logging.getLogger("orca-audio-themes")

_resume_timer_id: int | None = None

_EVENTS_TO_SUSPEND = [
    "object:state-changed:focused",
    "object:state-changed:showing",
    "object:children-changed:",
    "object:property-change:accessible-name",
]


def _suspend_events():
    global _resume_timer_id
    if _resume_timer_id is not None:
        GLib.source_remove(_resume_timer_id)
        _resume_timer_id = None
    try:
        from orca import event_manager
        manager = event_manager.get_manager()
        for event in _EVENTS_TO_SUSPEND:
            manager.deregister_listener(event)
    except Exception:
        pass


def _schedule_resume():
    global _resume_timer_id
    if _resume_timer_id is not None:
        GLib.source_remove(_resume_timer_id)
    _resume_timer_id = GLib.timeout_add(500, _resume_events)


def _resume_events():
    global _resume_timer_id
    _resume_timer_id = None
    try:
        from orca import event_manager
        manager = event_manager.get_manager()
        for event in _EVENTS_TO_SUSPEND:
            manager.register_listener(event)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# FocusManagedListBox (same pattern as Polyglot/Clock)
# ---------------------------------------------------------------------------

class FocusManagedListBox(Gtk.ListBox):
    """ListBox managing Tab/Shift+Tab focus between interactive widgets."""

    def __init__(self, focus_sidebar_func=None):
        super().__init__()
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.get_style_context().add_class("frame")
        self.set_can_focus(False)
        self.set_header_func(self._separator_header_func, None)
        self._widgets = []
        self._rows = []
        self._exiting_backward = [False]
        self._focus_sidebar_func = focus_sidebar_func

    @staticmethod
    def _separator_header_func(row, before, _user_data):
        if before is not None:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def add_row_with_widget(self, row, widget):
        widget.connect("key-press-event", self._on_widget_key_press)
        row.connect("focus-in-event", self._on_row_focus_in, widget)
        self.add(row)
        self._rows.append(row)
        self._widgets.append(widget)

    def _focus_next_sensitive_widget(self, widget):
        try:
            idx = self._widgets.index(widget)
            for i in range(idx + 1, len(self._widgets)):
                if self._widgets[i].get_sensitive():
                    self._widgets[i].grab_focus()
                    return True
        except ValueError:
            pass
        return False

    def _focus_prev_sensitive_widget(self, widget):
        try:
            idx = self._widgets.index(widget)
            for i in range(idx - 1, -1, -1):
                if self._widgets[i].get_sensitive():
                    self._widgets[i].grab_focus()
                    return True
            if self._rows:
                self._exiting_backward[0] = True
                self._rows[0].grab_focus()
        except ValueError:
            pass
        return False

    def _navigate_left_from_widget(self, widget):
        if isinstance(widget, (Gtk.Scale, Gtk.SpinButton)):
            return False
        if self._focus_sidebar_func:
            self._focus_sidebar_func()
            return True
        return False

    def _on_widget_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Tab:
            return self._focus_next_sensitive_widget(widget)
        if event.keyval == Gdk.KEY_ISO_Left_Tab:
            return self._focus_prev_sensitive_widget(widget)
        if event.keyval == Gdk.KEY_Left:
            return self._navigate_left_from_widget(widget)
        return False

    def _on_row_focus_in(self, _row, _event, widget):
        if self._exiting_backward[0]:
            self._exiting_backward[0] = False
            return False
        widget.grab_focus()
        return False


# ---------------------------------------------------------------------------
# Row creation helpers
# ---------------------------------------------------------------------------

def _create_switch_row(label_text, state, atk_name=None, atk_desc=None):
    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    hbox.set_margin_start(12)
    hbox.set_margin_end(12)
    hbox.set_margin_top(12)
    hbox.set_margin_bottom(12)
    label = Gtk.Label(label=label_text)
    label.set_use_underline(True)
    label.set_xalign(0)
    label.set_hexpand(True)
    switch = Gtk.Switch()
    switch.set_valign(Gtk.Align.CENTER)
    switch.set_active(state)
    label.set_mnemonic_widget(switch)
    atk_obj = switch.get_accessible()
    if atk_obj:
        atk_obj.set_role(Atk.Role.SWITCH)
        if atk_name:
            atk_obj.set_name(atk_name)
        if atk_desc:
            atk_obj.set_description(atk_desc)
    hbox.pack_start(label, True, True, 0)
    hbox.pack_end(switch, False, False, 0)
    row.add(hbox)
    return row, switch


def _create_combo_row(label_text, atk_name=None):
    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    hbox.set_margin_start(12)
    hbox.set_margin_end(12)
    hbox.set_margin_top(12)
    hbox.set_margin_bottom(12)
    label = Gtk.Label(label=label_text)
    label.set_use_underline(True)
    label.set_xalign(0)
    label.set_hexpand(True)
    combo = Gtk.ComboBoxText()
    label.set_mnemonic_widget(combo)
    atk_obj = combo.get_accessible()
    if atk_obj and atk_name:
        atk_obj.set_name(atk_name)
    hbox.pack_start(label, True, True, 0)
    hbox.pack_end(combo, False, False, 0)
    row.add(hbox)
    return row, combo


def _create_scale_row(label_text, lower, upper, step, value, atk_name=None):
    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    hbox.set_margin_start(12)
    hbox.set_margin_end(12)
    hbox.set_margin_top(12)
    hbox.set_margin_bottom(12)
    label = Gtk.Label(label=label_text)
    label.set_use_underline(True)
    label.set_xalign(0)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lower, upper, step)
    scale.set_draw_value(False)
    scale.set_value(value)
    scale.set_size_request(200, -1)
    label.set_mnemonic_widget(scale)
    atk_obj = scale.get_accessible()
    if atk_obj and atk_name:
        atk_obj.set_name(atk_name)
    hbox.pack_start(label, True, True, 0)
    hbox.pack_start(scale, True, True, 0)
    row.add(hbox)
    return row, scale


# ---------------------------------------------------------------------------
# Sound preview
# ---------------------------------------------------------------------------

_preview_lock = threading.Lock()
_preview_proc: subprocess.Popen | None = None


def _preview_sound(filepath: str, volume: float = 0.8) -> None:
    """Play a sound file in a background thread using pw-play."""
    global _preview_proc

    if not os.path.isfile(filepath):
        return

    def _worker():
        global _preview_proc
        with _preview_lock:
            if _preview_proc and _preview_proc.poll() is None:
                _preview_proc.terminate()
            try:
                _preview_proc = subprocess.Popen(
                    ["pw-play", "--volume", str(volume), filepath]
                )
                _preview_proc.wait(timeout=10)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Theme editor sound row
# ---------------------------------------------------------------------------

def _create_sound_row(sound_file, theme_dir, volume, is_enabled=True,
                      focus_sidebar_func=None):
    """Create a row for the theme editor: checkbox | label | Preview | Change | Reset."""
    label_text = SOUND_LABELS.get(sound_file, sound_file)
    current_path = os.path.join(theme_dir, sound_file)
    has_sound = os.path.isfile(current_path)

    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    hbox.set_margin_start(12)
    hbox.set_margin_end(12)
    hbox.set_margin_top(6)
    hbox.set_margin_bottom(6)

    # Enable checkbox
    check = Gtk.CheckButton()
    check.set_active(is_enabled)
    atk_check = check.get_accessible()
    if atk_check:
        atk_check.set_name(f"Enable {label_text} sound")
    hbox.pack_start(check, False, False, 0)

    label = Gtk.Label(label=label_text)
    label.set_xalign(0)
    label.set_hexpand(True)
    hbox.pack_start(label, True, True, 0)

    # Preview button
    preview_btn = Gtk.Button(label="Preview")
    preview_btn.set_sensitive(has_sound)
    atk_preview = preview_btn.get_accessible()
    if atk_preview:
        atk_preview.set_name(f"Preview {label_text} sound")

    def _on_preview(_btn):
        if os.path.isfile(current_path):
            _preview_sound(current_path, volume)

    preview_btn.connect("clicked", _on_preview)
    hbox.pack_start(preview_btn, False, False, 0)

    # Change button
    change_btn = Gtk.Button(label="Change")
    atk_change = change_btn.get_accessible()
    if atk_change:
        atk_change.set_name(f"Change {label_text} sound")

    def _on_change(_btn):
        dialog = Gtk.FileChooserDialog(
            title=f"Choose sound for {label_text}",
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Open", Gtk.ResponseType.OK)
        ff = Gtk.FileFilter()
        ff.set_name("Audio files")
        ff.add_pattern("*.wav")
        ff.add_pattern("*.ogg")
        dialog.add_filter(ff)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                dest = os.path.join(theme_dir, sound_file)
                try:
                    shutil.copy2(src, dest)
                    preview_btn.set_sensitive(True)
                except OSError as e:
                    _log.error("AudioThemes: failed to copy sound: %s", e)
        dialog.destroy()

    change_btn.connect("clicked", _on_change)
    hbox.pack_start(change_btn, False, False, 0)

    # Reset button
    reset_btn = Gtk.Button(label="Reset")
    atk_reset = reset_btn.get_accessible()
    if atk_reset:
        atk_reset.set_name(f"Reset {label_text} to default")

    def _on_reset(_btn):
        default_dir = os.path.join(THEMES_DIR, "default")
        default_path = os.path.join(default_dir, sound_file)
        if os.path.isfile(default_path) and theme_dir != default_dir:
            try:
                shutil.copy2(default_path, os.path.join(theme_dir, sound_file))
                preview_btn.set_sensitive(True)
            except OSError as e:
                _log.error("AudioThemes: failed to reset sound: %s", e)

    reset_btn.connect("clicked", _on_reset)
    hbox.pack_start(reset_btn, False, False, 0)

    row.add(hbox)
    # Return check as the focusable widget (first interactive element in the row)
    return row, check, sound_file


# ---------------------------------------------------------------------------
# Main settings window
# ---------------------------------------------------------------------------

class AudioThemesSettingsWindow(Gtk.Window):
    """Accessible settings window for Orca Audio Themes.

    Sidebar + Gtk.Stack layout matching Orca v50 preferences style.
    """

    def __init__(self, config: Config, on_save: Callable | None = None):
        super().__init__(title="Audio Themes Settings")
        self._config = config
        self._on_save = on_save

        self.set_default_size(750, 600)

        atk_obj = self.get_accessible()
        if atk_obj:
            atk_obj.set_name("Audio Themes Settings")

        _suspend_events()
        self._build_ui()
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key_press)

    def focus_sidebar(self):
        self._sidebar.grab_focus()
        _schedule_resume()

    def _build_ui(self):
        # Header bar
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.set_title("Audio Themes")
        self.set_titlebar(headerbar)

        save_btn = Gtk.Button(label="Save")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self._on_save_clicked)
        atk_save = save_btn.get_accessible()
        if atk_save:
            atk_save.set_name("Save settings")
        headerbar.pack_end(save_btn)

        # Main layout: sidebar | separator | content
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(main_box)

        # Sidebar
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_size_request(180, -1)

        self._sidebar = Gtk.ListBox()
        self._sidebar.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self._sidebar.get_style_context().add_class("navigation-sidebar")
        atk_sidebar = self._sidebar.get_accessible()
        if atk_sidebar:
            atk_sidebar.set_name("Settings categories")

        sidebar_scroll.add(self._sidebar)
        main_box.pack_start(sidebar_scroll, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(sep, False, False, 0)

        # Content stack
        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        content_scroll.add(self._stack)
        main_box.pack_start(content_scroll, True, True, 0)

        # Pages
        pages = [
            ("general", "General"),
            ("theme-editor", "Theme Editor"),
        ]
        for page_id, page_label in pages:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=page_label)
            label.set_xalign(0)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row.add(label)
            row._page_id = page_id
            self._sidebar.add(row)

        self._sidebar.connect("row-selected", self._on_sidebar_selected)

        self._stack.add_named(self._build_general_page(), "general")
        self._stack.add_named(self._build_theme_editor_page(), "theme-editor")

        first_row = self._sidebar.get_row_at_index(0)
        if first_row:
            self._sidebar.select_row(first_row)

    def _on_sidebar_selected(self, _listbox, row):
        if row and hasattr(row, "_page_id"):
            self._stack.set_visible_child_name(row._page_id)

    # --- General page ---

    def _build_general_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_border_width(24)
        page.set_margin_start(40)
        page.set_margin_end(40)

        listbox = FocusManagedListBox(self.focus_sidebar)

        # Enable
        row, self._enable_switch = _create_switch_row(
            "_Enable Audio Themes", self._config.enabled,
            atk_name="Enable audio themes",
        )
        listbox.add_row_with_widget(row, self._enable_switch)

        # Active theme
        row, self._theme_combo = _create_combo_row(
            "Active _theme:", atk_name="Active sound theme",
        )
        themes = self._config.list_themes()
        for theme in themes:
            self._theme_combo.append(theme["directory"], theme["name"])
        self._theme_combo.set_active_id(self._config.active_theme)
        if self._theme_combo.get_active() < 0 and themes:
            self._theme_combo.set_active(0)
        listbox.add_row_with_widget(row, self._theme_combo)

        # Volume
        row, self._volume_scale = _create_scale_row(
            "_Volume:", 0.0, 1.0, 0.05, self._config.volume,
            atk_name="Sound volume",
        )
        listbox.add_row_with_widget(row, self._volume_scale)

        # Positional audio
        row, self._positional_switch = _create_switch_row(
            "_Positional audio (2D)", self._config.positional_audio,
            atk_name="Enable positional audio",
            atk_desc="Pans sounds left-right and adjusts tone based on screen position",
        )
        listbox.add_row_with_widget(row, self._positional_switch)

        # Play on focus
        row, self._focus_switch = _create_switch_row(
            "Play on _focus change", self._config.play_on_focus,
            atk_name="Play sounds on focus change",
        )
        listbox.add_row_with_widget(row, self._focus_switch)

        # Play on mode change
        row, self._mode_switch = _create_switch_row(
            "Play on _mode change", self._config.play_on_mode_change,
            atk_name="Play sounds on mode change",
        )
        listbox.add_row_with_widget(row, self._mode_switch)

        # Speak roles
        row, self._speak_switch = _create_switch_row(
            "_Speak role names", self._config.speak_roles,
            atk_name="Speak role names alongside sounds",
        )
        listbox.add_row_with_widget(row, self._speak_switch)

        page.pack_start(listbox, True, True, 0)
        return page

    # --- Theme editor page ---

    def _build_theme_editor_page(self):
        self._sound_checks: dict[str, Gtk.CheckButton] = {}

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(24)
        page.set_margin_start(20)
        page.set_margin_end(20)

        # Theme management buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        new_btn = Gtk.Button(label="New Theme")
        atk_new = new_btn.get_accessible()
        if atk_new:
            atk_new.set_name("Create a new theme by duplicating the current one")
        new_btn.connect("clicked", self._on_new_theme)
        btn_box.pack_start(new_btn, False, False, 0)

        import_btn = Gtk.Button(label="Import")
        atk_import = import_btn.get_accessible()
        if atk_import:
            atk_import.set_name("Import a theme package")
        import_btn.connect("clicked", self._on_import_theme)
        btn_box.pack_start(import_btn, False, False, 0)

        export_btn = Gtk.Button(label="Export")
        atk_export = export_btn.get_accessible()
        if atk_export:
            atk_export.set_name("Export current theme as a package")
        export_btn.connect("clicked", self._on_export_theme)
        btn_box.pack_start(export_btn, False, False, 0)

        page.pack_start(btn_box, False, False, 0)

        # Sound list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        listbox = FocusManagedListBox(self.focus_sidebar)
        theme_dir = self._config.theme_dir
        volume = self._config.volume
        disabled = set(self._config.disabled_sounds)

        for sound_file in ALL_SOUND_FILES:
            is_enabled = sound_file not in disabled
            row, check, sfile = _create_sound_row(
                sound_file, theme_dir, volume, is_enabled, self.focus_sidebar,
            )
            self._sound_checks[sfile] = check
            listbox.add_row_with_widget(row, check)

        scroll.add(listbox)
        page.pack_start(scroll, True, True, 0)
        return page

    # --- Theme management ---

    def _on_new_theme(self, _btn):
        dialog = Gtk.Dialog(
            title="New Theme",
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Create", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_border_width(12)
        content.set_spacing(8)

        label = Gtk.Label(label="Theme name:")
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        atk_entry = entry.get_accessible()
        if atk_entry:
            atk_entry.set_name("New theme name")
        content.pack_start(label, False, False, 0)
        content.pack_start(entry, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content.show_all()

        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            # Sanitise name for directory
            dir_name = name.lower().replace(" ", "_")
            new_dir = os.path.join(THEMES_DIR, dir_name)
            src_dir = self._config.theme_dir
            if os.path.isdir(src_dir) and not os.path.exists(new_dir):
                try:
                    shutil.copytree(src_dir, new_dir)
                    # Update info.json
                    import json
                    info_path = os.path.join(new_dir, "info.json")
                    info = {"name": name, "summary": f"Custom theme based on {self._config.active_theme}", "author": ""}
                    with open(info_path, "w") as f:
                        json.dump(info, f, indent=4)
                    # Update combo
                    self._theme_combo.append(dir_name, name)
                    self._theme_combo.set_active_id(dir_name)
                except OSError as e:
                    _log.error("AudioThemes: failed to create theme: %s", e)

    def _on_import_theme(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title="Import Theme Package",
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Import", Gtk.ResponseType.OK)
        ff = Gtk.FileFilter()
        ff.set_name("Theme packages (*.zip, *.atp)")
        ff.add_pattern("*.zip")
        ff.add_pattern("*.atp")
        dialog.add_filter(ff)

        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and filename:
            import json
            import zipfile
            try:
                with zipfile.ZipFile(filename) as zf:
                    # Determine theme name from info.json inside archive
                    info_names = [n for n in zf.namelist() if n.endswith("info.json")]
                    theme_name = os.path.splitext(os.path.basename(filename))[0]
                    if info_names:
                        with zf.open(info_names[0]) as f:
                            info = json.load(f)
                            theme_name = info.get("name", theme_name)
                    dir_name = theme_name.lower().replace(" ", "_")
                    dest = os.path.join(THEMES_DIR, dir_name)
                    os.makedirs(dest, exist_ok=True)
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if not basename:
                            continue
                        # Translate NVDA numeric filenames to descriptive names
                        name_no_ext, ext = os.path.splitext(basename)
                        if ext.lower() in (".wav", ".ogg"):
                            try:
                                nvda_id = int(name_no_ext)
                                if nvda_id in NVDA_ID_TO_FILENAME:
                                    basename = NVDA_ID_TO_FILENAME[nvda_id]
                            except ValueError:
                                pass  # Already a descriptive name
                        with zf.open(member) as src, open(os.path.join(dest, basename), "wb") as dst:
                            dst.write(src.read())
                    self._theme_combo.append(dir_name, theme_name)
            except (zipfile.BadZipFile, OSError, json.JSONDecodeError) as e:
                _log.error("AudioThemes: failed to import theme: %s", e)

    def _on_export_theme(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title="Export Theme Package",
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Export", Gtk.ResponseType.OK)
        dialog.set_current_name(f"{self._config.active_theme}.zip")
        dialog.set_do_overwrite_confirmation(True)

        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and filename:
            import zipfile
            theme_dir = self._config.theme_dir
            if os.path.isdir(theme_dir):
                try:
                    with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in os.listdir(theme_dir):
                            fpath = os.path.join(theme_dir, f)
                            if os.path.isfile(fpath):
                                zf.write(fpath, f)
                except OSError as e:
                    _log.error("AudioThemes: failed to export theme: %s", e)

    # --- Save/close ---

    def _on_save_clicked(self, _btn):
        self._save_config()
        _suspend_events()
        self.destroy()
        _schedule_resume()

    def _on_delete(self, _window, _event):
        _suspend_events()
        _schedule_resume()
        return False

    def _on_key_press(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            _suspend_events()
            self.destroy()
            _schedule_resume()
            return True
        return False

    def _save_config(self):
        self._config.enabled = self._enable_switch.get_active()
        theme_id = self._theme_combo.get_active_id()
        if theme_id:
            self._config.active_theme = theme_id
        self._config.volume = self._volume_scale.get_value()
        self._config.positional_audio = self._positional_switch.get_active()
        self._config.play_on_focus = self._focus_switch.get_active()
        self._config.play_on_mode_change = self._mode_switch.get_active()
        self._config.speak_roles = self._speak_switch.get_active()
        # Collect disabled sounds from theme editor checkboxes
        disabled = []
        for sfile, check in self._sound_checks.items():
            if not check.get_active():
                disabled.append(sfile)
        self._config.disabled_sounds = disabled
        self._config.save()

        if self._on_save:
            self._on_save(self._config)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def show_settings_dialog(config: Config, on_save: Callable | None = None):
    """Show the settings window. Must be called from the GTK main thread."""
    window = AudioThemesSettingsWindow(config, on_save)
    window.show_all()
    return window
