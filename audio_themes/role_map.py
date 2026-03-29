"""Mapping from AT-SPI roles to sound filenames.

Each Atspi.Role constant maps to a WAV filename within the active theme
directory.  Roles not listed here produce no sound.

The NVDA_ID_TO_FILENAME dict documents the original NVDA controlTypes.Role
numeric values so the correct sound file is used for each role.

NVDA controlTypes.Role enum (from nvaccess/nvda source):
  5=CHECKBOX, 6=RADIOBUTTON, 8=EDITABLETEXT, 9=BUTTON, 11=MENUITEM,
  12=POPUPMENU, 13=COMBOBOX, 14=LIST, 15=LISTITEM, 19=LINK,
  20=TREEVIEW, 21=TREEVIEWITEM, 22=TAB, 24=SLIDER, 29=TABLECELL,
  35=TOOLBAR, 36=DROPDOWNBUTTON, 37=CLOCK, 60=CHECKMENUITEM,
  61=DATEEDITOR, 76=RADIOMENUITEM, 82=TERMINAL, 83=RICHEDIT,
  92=TOGGLEBUTTON, 100=DROPLIST, 102=MENUBUTTON,
  103=DROPDOWNBUTTONGRID, 108=SPINBUTTON, 123=PASSWORDEDIT
  2500=protected, 2501=first, 2502=last, 2503=notify, 2504=loaded
"""

from __future__ import annotations

import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi


# --- NVDA numeric ID -> descriptive filename --------------------------------

NVDA_ID_TO_FILENAME: dict[int, str] = {
    5:   "checkbox.wav",          # CHECKBOX
    6:   "radio_button.wav",      # RADIOBUTTON
    8:   "entry.wav",             # EDITABLETEXT
    9:   "button.wav",            # BUTTON
    11:  "menu_item.wav",         # MENUITEM
    12:  "popup_menu.wav",        # POPUPMENU
    13:  "combo_box.wav",         # COMBOBOX
    14:  "list.wav",              # LIST
    15:  "list_item.wav",         # LISTITEM
    19:  "link.wav",              # LINK
    20:  "tree_view.wav",         # TREEVIEW
    21:  "tree_item.wav",         # TREEVIEWITEM
    22:  "page_tab.wav",          # TAB
    24:  "slider.wav",            # SLIDER
    29:  "table_cell.wav",        # TABLECELL
    35:  "toolbar.wav",           # TOOLBAR
    36:  "dropdown_button.wav",   # DROPDOWNBUTTON
    37:  "clock.wav",             # CLOCK
    60:  "checked_menu_item.wav", # CHECKMENUITEM
    61:  "date_editor.wav",       # DATEEDITOR
    76:  "radio_menu_item.wav",   # RADIOMENUITEM
    82:  "terminal.wav",          # TERMINAL
    83:  "rich_edit.wav",         # RICHEDIT
    92:  "toggle_button.wav",     # TOGGLEBUTTON
    100: "drop_list.wav",         # DROPLIST
    102: "menu_button.wav",       # MENUBUTTON
    103: "dropdown_button_grid.wav",  # DROPDOWNBUTTONGRID
    108: "spin_button.wav",       # SPINBUTTON
    123: "password.wav",          # PASSWORDEDIT
    # Special props (non-role, context-triggered)
    2500: "protected_field.wav",
    2501: "first_item.wav",
    2502: "last_item.wav",
    2503: "notification.wav",
    2504: "page_loaded.wav",
}


# --- AT-SPI Role -> sound filename -----------------------------------------
# Maps Orca AT-SPI roles to the closest NVDA sound.

ROLE_TO_SOUND: dict[Atspi.Role, str] = {
    # Buttons — NVDA 9=BUTTON
    Atspi.Role.PUSH_BUTTON:        "button.wav",
    Atspi.Role.BUTTON:             "button.wav",
    # Check boxes — NVDA 5=CHECKBOX
    Atspi.Role.CHECK_BOX:          "checkbox.wav",
    # Radio buttons — NVDA 6=RADIOBUTTON
    Atspi.Role.RADIO_BUTTON:       "radio_button.wav",
    # Radio menu item — NVDA 76=RADIOMENUITEM
    Atspi.Role.RADIO_MENU_ITEM:    "radio_menu_item.wav",
    # Text entry — NVDA 8=EDITABLETEXT
    Atspi.Role.ENTRY:              "entry.wav",
    Atspi.Role.TEXT:                "entry.wav",
    Atspi.Role.EDITBAR:            "entry.wav",
    # Rich text / document editing — NVDA 83=RICHEDIT
    # (falls back to entry if rich_edit.wav missing)
    # Password — NVDA 123=PASSWORDEDIT
    Atspi.Role.PASSWORD_TEXT:       "password.wav",
    # Combo box — NVDA 13=COMBOBOX
    Atspi.Role.COMBO_BOX:          "combo_box.wav",
    # Link — NVDA 19=LINK
    Atspi.Role.LINK:               "link.wav",
    # Menu item — NVDA 11=MENUITEM
    Atspi.Role.MENU_ITEM:          "menu_item.wav",
    # Checked menu item — NVDA 60=CHECKMENUITEM
    Atspi.Role.CHECK_MENU_ITEM:    "checked_menu_item.wav",
    # Menu / popup menu — NVDA 12=POPUPMENU
    Atspi.Role.MENU:               "popup_menu.wav",
    Atspi.Role.POPUP_MENU:         "popup_menu.wav",
    # Menu bar — reuse popup_menu sound (no dedicated NVDA sound for MENUBAR=10)
    Atspi.Role.MENU_BAR:           "popup_menu.wav",
    # Lists — NVDA 14=LIST
    Atspi.Role.LIST:               "list.wav",
    Atspi.Role.LIST_BOX:           "list.wav",
    # List items — NVDA 15=LISTITEM
    Atspi.Role.LIST_ITEM:          "list_item.wav",
    # Table cell — NVDA 29=TABLECELL
    Atspi.Role.TABLE_CELL:         "table_cell.wav",
    # Tree view — NVDA 20=TREEVIEW
    Atspi.Role.TREE:               "tree_view.wav",
    Atspi.Role.TREE_TABLE:         "tree_view.wav",
    # Tree items — NVDA 21=TREEVIEWITEM
    Atspi.Role.TREE_ITEM:          "tree_item.wav",
    # Tabs — NVDA 22=TAB
    Atspi.Role.PAGE_TAB:           "page_tab.wav",
    # Tab list — reuse page_tab sound (no dedicated NVDA sound for TABCONTROL=23)
    Atspi.Role.PAGE_TAB_LIST:      "page_tab.wav",
    # Slider — NVDA 24=SLIDER
    Atspi.Role.SLIDER:             "slider.wav",
    Atspi.Role.SCROLL_BAR:         "slider.wav",
    # Spin button — NVDA 108=SPINBUTTON
    Atspi.Role.SPIN_BUTTON:        "spin_button.wav",
    # Toggle button — NVDA 92=TOGGLEBUTTON
    Atspi.Role.TOGGLE_BUTTON:      "toggle_button.wav",
    # Switch — reuse toggle_button sound (closest match)
    Atspi.Role.SWITCH:             "toggle_button.wav",
    # Toolbar — NVDA 35=TOOLBAR
    Atspi.Role.TOOL_BAR:           "toolbar.wav",
    # Terminal — NVDA 82=TERMINAL
    Atspi.Role.TERMINAL:           "terminal.wav",
    # Dialog / alert — reuse drop_list sound (NVDA 100=DROPLIST is closest)
    Atspi.Role.DIALOG:             "drop_list.wav",
    Atspi.Role.FILE_CHOOSER:       "drop_list.wav",
    Atspi.Role.ALERT:              "notification.wav",
    # Notification
    Atspi.Role.NOTIFICATION:       "notification.wav",
    # Image — reuse clock sound (NVDA 37=CLOCK, no dedicated image sound)
    Atspi.Role.IMAGE:              "clock.wav",
    # Status bar — reuse toolbar sound (closest available)
    Atspi.Role.STATUS_BAR:         "toolbar.wav",
    # Progress bar — reuse slider sound (closest available)
    Atspi.Role.PROGRESS_BAR:       "slider.wav",
    # Heading — no dedicated NVDA sound; reuse link (distinctive & common in browse mode)
    # Column/row headers — reuse table_cell
    Atspi.Role.COLUMN_HEADER:      "table_cell.wav",
    Atspi.Role.TABLE_COLUMN_HEADER: "table_cell.wav",
    Atspi.Role.ROW_HEADER:         "table_cell.wav",
    Atspi.Role.TABLE_ROW_HEADER:   "table_cell.wav",
    # Document — reuse rich_edit sound (NVDA 83=RICHEDIT)
    Atspi.Role.DOCUMENT_FRAME:     "rich_edit.wav",
    Atspi.Role.DOCUMENT_WEB:       "rich_edit.wav",
}

# Mode-change sounds (not role-based)
MODE_SOUNDS: dict[str, str] = {
    "focus_mode":         "focus_mode.wav",
    "browse_mode":        "browse_mode.wav",
    "focus_mode_sticky":  "focus_mode_sticky.wav",
    "browse_mode_sticky": "browse_mode_sticky.wav",
    "window_activate":    "window_activate.wav",
}

# All sound filenames that a complete theme should provide
ALL_SOUND_FILES: list[str] = sorted(
    set(ROLE_TO_SOUND.values()) | set(MODE_SOUNDS.values())
    | {"first_item.wav", "last_item.wav", "page_loaded.wav", "protected_field.wav"}
)

# Human-readable labels for the theme editor UI
SOUND_LABELS: dict[str, str] = {
    "button.wav":              "Button",
    "checkbox.wav":            "Check box",
    "radio_button.wav":        "Radio button",
    "radio_menu_item.wav":     "Radio menu item",
    "entry.wav":               "Text entry",
    "rich_edit.wav":           "Rich text / document",
    "password.wav":            "Password field",
    "protected_field.wav":     "Protected field",
    "combo_box.wav":           "Combo box",
    "link.wav":                "Link",
    "menu_item.wav":           "Menu item",
    "checked_menu_item.wav":   "Checked menu item",
    "popup_menu.wav":          "Menu / popup menu",
    "menu_button.wav":         "Menu button",
    "list.wav":                "List",
    "list_item.wav":           "List item",
    "table_cell.wav":          "Table cell / header",
    "tree_view.wav":           "Tree view",
    "tree_item.wav":           "Tree item",
    "page_tab.wav":            "Page tab",
    "slider.wav":              "Slider / scroll bar",
    "spin_button.wav":         "Spin button",
    "toggle_button.wav":       "Toggle button / switch",
    "toolbar.wav":             "Toolbar / status bar",
    "terminal.wav":            "Terminal",
    "drop_list.wav":           "Drop list / dialog",
    "dropdown_button.wav":     "Drop-down button",
    "dropdown_button_grid.wav": "Drop-down button grid",
    "date_editor.wav":         "Date editor",
    "clock.wav":               "Clock / image",
    "notification.wav":        "Notification / alert",
    "first_item.wav":          "First item in list",
    "last_item.wav":           "Last item in list",
    "page_loaded.wav":         "Page loaded",
    "focus_mode.wav":          "Focus mode",
    "browse_mode.wav":         "Browse mode",
    "focus_mode_sticky.wav":   "Sticky focus mode",
    "browse_mode_sticky.wav":  "Sticky browse mode",
    "window_activate.wav":     "Window activated",
}
