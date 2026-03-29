#!/usr/bin/env bash
# Orca Audio Themes — Uninstaller
set -euo pipefail

ADDON_NAME="audio_themes"
ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
ADDON_DIR="$ORCA_DIR/$ADDON_NAME"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"
SCHEMA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/glib-2.0/schemas"
SCHEMA_FILE="org.gnome.Orca.AudioThemes.gschema.xml"

BEGIN_MARKER="# --- audio-themes begin ---"
END_MARKER="# --- audio-themes end ---"

info()  { echo "  [+] $*"; }

echo ""
echo "=== Orca Audio Themes — Uninstaller ==="
echo ""

# Remove loader block from customizations
if [ -f "$CUSTOMIZATIONS" ] && grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    info "Removed Audio Themes loader block from orca-customizations.py."
fi

# Remove add-on directory
if [ -d "$ADDON_DIR" ]; then
    rm -rf "$ADDON_DIR"
    info "Removed $ADDON_DIR"
fi

# Remove GSettings schema
if [ -f "$SCHEMA_DIR/$SCHEMA_FILE" ]; then
    rm -f "$SCHEMA_DIR/$SCHEMA_FILE"
    if command -v glib-compile-schemas >/dev/null 2>&1; then
        glib-compile-schemas "$SCHEMA_DIR" 2>/dev/null || true
    fi
    info "Removed GSettings schema."
fi

# Clear dconf settings
if command -v dconf >/dev/null 2>&1; then
    dconf reset -f /org/gnome/orca/audio-themes/ 2>/dev/null || true
    info "Cleared dconf settings."
fi

echo ""
echo "=== Uninstallation complete! ==="
echo ""
echo "  Restart Orca to finish: orca --replace &"
echo ""
