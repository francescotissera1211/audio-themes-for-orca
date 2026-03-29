"""GSettings-backed configuration for Orca Audio Themes."""

from __future__ import annotations

import json
import logging
import os

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

_log = logging.getLogger("orca-audio-themes")

SCHEMA_ID = "org.gnome.Orca.AudioThemes"

XDG_DATA_HOME = os.environ.get(
    "XDG_DATA_HOME", os.path.expanduser("~/.local/share")
)
ORCA_DIR = os.path.join(XDG_DATA_HOME, "orca")
THEMES_DIR = os.path.join(ORCA_DIR, "audio_themes", "themes")


def _get_schema_source():
    """Get a GSettings schema source that includes the user schema dir."""
    user_schema_dir = os.path.join(XDG_DATA_HOME, "glib-2.0", "schemas")
    default_source = Gio.SettingsSchemaSource.get_default()
    try:
        return Gio.SettingsSchemaSource.new_from_directory(
            user_schema_dir, default_source, False,
        )
    except GLib.Error:
        return default_source


class Config:
    """Audio Themes configuration backed by GSettings."""

    def __init__(self):
        self.enabled: bool = True
        self.active_theme: str = "default"
        self.positional_audio: bool = True
        self.volume: float = 0.8
        self.play_on_focus: bool = True
        self.play_on_mode_change: bool = True
        self.speak_roles: bool = True
        self.disabled_sounds: list[str] = []
        self._settings: Gio.Settings | None = None

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        cfg._init_gsettings()
        return cfg

    def _init_gsettings(self):
        source = _get_schema_source()
        schema = source.lookup(SCHEMA_ID, True)
        if schema is None:
            _log.warning(
                "AudioThemes: GSettings schema %s not found, using defaults",
                SCHEMA_ID,
            )
            return
        self._settings = Gio.Settings.new_full(schema, None, None)
        self.enabled = self._settings.get_boolean("enabled")
        self.active_theme = self._settings.get_string("active-theme")
        self.positional_audio = self._settings.get_boolean("positional-audio")
        self.volume = self._settings.get_double("volume")
        self.play_on_focus = self._settings.get_boolean("play-on-focus")
        self.play_on_mode_change = self._settings.get_boolean("play-on-mode-change")
        self.speak_roles = self._settings.get_boolean("speak-roles")
        self.disabled_sounds = list(self._settings.get_strv("disabled-sounds"))

    def save(self):
        if self._settings is None:
            _log.error("AudioThemes: cannot save, GSettings not available")
            return
        self._settings.set_boolean("enabled", self.enabled)
        self._settings.set_string("active-theme", self.active_theme)
        self._settings.set_boolean("positional-audio", self.positional_audio)
        self._settings.set_double("volume", self.volume)
        self._settings.set_boolean("play-on-focus", self.play_on_focus)
        self._settings.set_boolean("play-on-mode-change", self.play_on_mode_change)
        self._settings.set_boolean("speak-roles", self.speak_roles)
        self._settings.set_strv("disabled-sounds", self.disabled_sounds)

    @property
    def theme_dir(self) -> str:
        """Absolute path to the active theme directory."""
        return os.path.join(THEMES_DIR, self.active_theme)

    def list_themes(self) -> list[dict]:
        """Return a list of installed themes with metadata."""
        themes = []
        if not os.path.isdir(THEMES_DIR):
            return themes
        for name in sorted(os.listdir(THEMES_DIR)):
            theme_path = os.path.join(THEMES_DIR, name)
            if not os.path.isdir(theme_path):
                continue
            info_path = os.path.join(theme_path, "info.json")
            info = {"name": name, "directory": name, "summary": "", "author": ""}
            if os.path.isfile(info_path):
                try:
                    with open(info_path) as f:
                        data = json.load(f)
                    info.update(data)
                    info["directory"] = name
                except (json.JSONDecodeError, OSError):
                    pass
            themes.append(info)
        return themes

    def list_theme_sounds(self, theme_name: str | None = None) -> list[str]:
        """Return sorted list of sound files in a theme."""
        theme = theme_name or self.active_theme
        theme_path = os.path.join(THEMES_DIR, theme)
        if not os.path.isdir(theme_path):
            return []
        return sorted(
            f for f in os.listdir(theme_path)
            if f.lower().endswith((".wav", ".ogg"))
        )
