# Orca Audio Themes

Sound theme support for the [Orca screen reader](https://wiki.gnome.org/Projects/Orca) on Linux. Plays distinct sounds when different UI elements receive focus and when Orca switches between focus/browse modes — equivalent to the [Audio Themes add-on](https://github.com/mush42/NVDA-Audio-Themes) for NVDA on Windows.

## Features

- **Role-based focus sounds** — each UI control type (button, checkbox, link, slider, etc.) plays a unique sound when it receives focus
- **Mode-change sounds** — audible feedback when switching between focus and browse modes
- **2D positional audio** — sounds pan left/right and shift tone based on the focused element's screen position
- **Theme support** — installable sound themes with a built-in editor for creating custom themes
- **Settings GUI** — full configuration dialog accessible via Orca+Ctrl+A
- **Non-invasive** — uses `orca-customizations.py` and GSettings; no Orca source code is modified

## Requirements

- Orca screen reader
- GStreamer 1.0 with `gst-plugins-good` (for `audiopanorama` and `equalizer-3bands`)
- PipeWire (for `pw-play` in sound preview)
- `sox` (optional, for generating mode-change sounds during install)

## Installation

```bash
git clone <this-repo>
cd orca-audio-themes
./install.sh
```

Then restart Orca:

```bash
orca --replace &
```

## Uninstallation

```bash
./uninstall.sh
orca --replace &
```

## Usage

After installation, sounds play automatically as you navigate UI elements:

- **Tab** through a GTK app (e.g., GNOME Settings) — each button, checkbox, combo box, etc. plays a distinct sound
- **Navigate a web page** in Firefox — hear the difference between links, headings, form controls
- **Toggle focus/browse mode** with Insert+A — mode-change sounds play

### Keybinding

| Shortcut | Action |
|----------|--------|
| Orca+Ctrl+A | Open Audio Themes settings |

### Settings

The settings dialog (Orca+Ctrl+A) has two pages:

**General:**
- Enable/disable audio themes
- Choose active sound theme
- Volume control
- Toggle 2D positional audio
- Toggle focus-change and mode-change sounds
- Toggle whether Orca still speaks role names

**Theme Editor:**
- Preview, change, or reset sounds for each role
- Create new themes (duplicates current theme)
- Import/export themes as ZIP packages (compatible with NVDA `.atp` format)

## How It Works

The add-on monkey-patches two Orca internal methods without modifying any source files:

1. **`FocusManager.set_locus_of_focus`** — intercepted to play role-appropriate sounds on focus changes
2. **`DocumentPresenter._set_presentation_mode`** (and sticky variants) — intercepted for mode-change sounds

Sound playback uses a custom GStreamer pipeline:

```
filesrc → decodebin → audioconvert → equalizer-3bands → audiopanorama → volume → autoaudiosink
```

- **Horizontal panning** (`audiopanorama`): maps X screen position to stereo pan
- **Vertical tone shift** (`equalizer-3bands`): objects near the top sound brighter, objects near the bottom sound warmer

Configuration is stored via GSettings at `org.gnome.Orca.AudioThemes`.

## Creating Custom Themes

A theme is a directory containing WAV files named after UI roles. Place your theme in `~/.local/share/orca/audio_themes/themes/<your-theme>/` with an `info.json`:

```json
{
    "name": "My Theme",
    "summary": "A custom audio theme",
    "author": "Your Name"
}
```

Sound files should be short (50-200ms) WAV files. See the `default` theme for the complete list of filenames.

You can also use the Theme Editor (Orca+Ctrl+A → Theme Editor page) to change individual sounds without manual file management.

## Credits

- **Default theme sounds**: sourced from the [NVDA Audio Themes](https://github.com/mush42/NVDA-Audio-Themes) add-on (GPL v2+), originally from the Unspoken add-on by Austin Hicks and Bryan Smart, and TWBlue
- **Original NVDA add-on**: Musharraf Omer
- **Concept**: Inspired by NVDA's audio themes / Unspoken 3D Audio

## License

GNU General Public License v2.0 — see [COPYING](COPYING).
