#!/usr/bin/env bash
# Orca Audio Themes — Installer
set -euo pipefail

ADDON_NAME="audio_themes"
ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
ADDON_DIR="$ORCA_DIR/$ADDON_NAME"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/$ADDON_NAME"
SCHEMA_FILE="org.gnome.Orca.AudioThemes.gschema.xml"
SCHEMA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/glib-2.0/schemas"

BEGIN_MARKER="# --- audio-themes begin ---"
END_MARKER="# --- audio-themes end ---"

info()  { echo "  [+] $*"; }
warn()  { echo "  [!] $*"; }
error() { echo "  [ERROR] $*" >&2; exit 1; }

echo ""
echo "=== Orca Audio Themes — Installer ==="
echo ""

# Pre-flight
if ! python3 -c "import orca" 2>/dev/null; then
    error "Orca screen reader not found. Please install Orca first."
fi
info "Orca found."

if [ ! -d "$SOURCE_DIR" ]; then
    error "Source directory '$SOURCE_DIR' not found."
fi

# Install add-on files
info "Installing add-on files to $ADDON_DIR..."
mkdir -p "$ADDON_DIR"
cp "$SOURCE_DIR"/__init__.py "$ADDON_DIR/"
cp "$SOURCE_DIR"/role_map.py "$ADDON_DIR/"
cp "$SOURCE_DIR"/sound_player.py "$ADDON_DIR/"
cp "$SOURCE_DIR"/focus_interceptor.py "$ADDON_DIR/"
cp "$SOURCE_DIR"/config.py "$ADDON_DIR/"
cp "$SOURCE_DIR"/config_ui.py "$ADDON_DIR/"
info "Python modules installed."

# Install sound themes
if [ -d "$SOURCE_DIR/themes" ]; then
    info "Installing sound themes..."
    mkdir -p "$ADDON_DIR/themes"
    cp -r "$SOURCE_DIR/themes/"* "$ADDON_DIR/themes/"
    THEME_COUNT=$(find "$ADDON_DIR/themes" -mindepth 1 -maxdepth 1 -type d | wc -l)
    info "$THEME_COUNT theme(s) installed."
else
    warn "No themes directory found."
fi

# Regenerate mode-change sounds with sox if available (otherwise the
# pre-generated versions shipped in the repo are used).
THEME_DEFAULT="$ADDON_DIR/themes/default"
if command -v sox >/dev/null 2>&1; then
    info "Regenerating mode-change sounds with sox..."
    # focus_mode.wav — ascending two-tone (400Hz -> 600Hz, 100ms)
    sox -n -r 44100 -c 1 "$THEME_DEFAULT/focus_mode.wav" \
        synth 0.05 sine 400 synth 0.05 sine 600 2>/dev/null || true
    # browse_mode.wav — descending two-tone (600Hz -> 400Hz, 100ms)
    sox -n -r 44100 -c 1 "$THEME_DEFAULT/browse_mode.wav" \
        synth 0.05 sine 600 synth 0.05 sine 400 2>/dev/null || true
    # focus_mode_sticky.wav — ascending three-tone
    sox -n -r 44100 -c 1 "$THEME_DEFAULT/focus_mode_sticky.wav" \
        synth 0.04 sine 400 synth 0.04 sine 550 synth 0.04 sine 700 2>/dev/null || true
    # browse_mode_sticky.wav — descending three-tone
    sox -n -r 44100 -c 1 "$THEME_DEFAULT/browse_mode_sticky.wav" \
        synth 0.04 sine 700 synth 0.04 sine 550 synth 0.04 sine 400 2>/dev/null || true
    info "Mode-change sounds regenerated."
fi

# Install GSettings schema
if [ -f "$SOURCE_DIR/$SCHEMA_FILE" ]; then
    info "Installing GSettings schema..."
    mkdir -p "$SCHEMA_DIR"
    cp "$SOURCE_DIR/$SCHEMA_FILE" "$SCHEMA_DIR/"
    if command -v glib-compile-schemas >/dev/null 2>&1; then
        glib-compile-schemas "$SCHEMA_DIR" 2>/dev/null && \
            info "GSettings schema compiled." || \
            warn "Could not compile GSettings schema."
    else
        warn "glib-compile-schemas not found."
    fi
else
    warn "GSettings schema file not found."
fi

# Set up orca-customizations.py
LOADER_BLOCK="${BEGIN_MARKER}
try:
    import sys as _sys, os as _os
    _orca_dir = _os.path.join(
        _os.environ.get(\"XDG_DATA_HOME\", _os.path.expanduser(\"~/.local/share\")),
        \"orca\"
    )
    if _orca_dir not in _sys.path:
        _sys.path.insert(0, _orca_dir)
    from audio_themes.focus_interceptor import install as _audio_themes_install
    _audio_themes_install()
except Exception as _e:
    import logging as _logging
    _logging.getLogger(\"orca-audio-themes\").error(
        f\"Failed to load Audio Themes: {_e}\", exc_info=True
    )
${END_MARKER}"

# Create customizations file if needed
if [ ! -f "$CUSTOMIZATIONS" ]; then
    touch "$CUSTOMIZATIONS"
    info "Created $CUSTOMIZATIONS"
fi

# Remove any previous audio-themes block
if grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    info "Removed previous Audio Themes loader block."
fi

# Append the loader block
if [ -s "$CUSTOMIZATIONS" ] && grep -q '[^[:space:]]' "$CUSTOMIZATIONS" 2>/dev/null; then
    echo "" >> "$CUSTOMIZATIONS"
    echo "$LOADER_BLOCK" >> "$CUSTOMIZATIONS"
    info "Loader appended to existing orca-customizations.py."
else
    echo "$LOADER_BLOCK" > "$CUSTOMIZATIONS"
    info "Created orca-customizations.py with loader."
fi

echo ""
echo "=== Installation complete! ==="
echo ""
echo "  Restart Orca for changes to take effect:"
echo "    orca --replace &"
echo ""
echo "  Settings: press Orca+Ctrl+A at any time."
echo "  Uninstall: run ./uninstall.sh"
echo ""
