# SPDX-License-Identifier: GPL-3.0-or-later
# Keyboard shortcuts window

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gdk


class ShortcutsWindow(Adw.Window):
    """Window for displaying keyboard shortcuts."""
    
    def __init__(self, parent):
        """
        Args:
            parent: Parent window
        """
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Keyboard Shortcuts",
            default_width=600,
            default_height=700,
        )
        
        self.build_ui()
    
    def build_ui(self):
        """Build the shortcuts window UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Scrolled content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # Content box with margins
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        scrolled.set_child(content_box)
        main_box.append(scrolled)
        
        # Process Management shortcuts
        process_group = Adw.PreferencesGroup()
        process_group.set_title("Process Management")
        content_box.append(process_group)
        
        self.add_shortcut_row(process_group, "End Process", "Delete")
        self.add_shortcut_row(process_group, "Force Kill Process", "Shift+Delete")
        self.add_shortcut_row(process_group, "Show Process Details", "Enter")
        self.add_shortcut_row(process_group, "Select All Filtered Processes", "Enter (in search)")
        
        # Navigation shortcuts
        nav_group = Adw.PreferencesGroup()
        nav_group.set_title("Navigation")
        content_box.append(nav_group)
        
        self.add_shortcut_row(nav_group, "Switch Tabs", "Ctrl+Tab")
        self.add_shortcut_row(nav_group, "Toggle Search/Filter", "Ctrl+F")
        self.add_shortcut_row(nav_group, "Close Search", "Escape")
        
        # Application shortcuts
        app_group = Adw.PreferencesGroup()
        app_group.set_title("Application")
        content_box.append(app_group)
        
        self.add_shortcut_row(app_group, "Refresh Process List", "F5")
        self.add_shortcut_row(app_group, "Toggle Auto-Refresh", "Space")
        self.add_shortcut_row(app_group, "Open Preferences", "Ctrl+,")
        self.add_shortcut_row(app_group, "Show Keyboard Shortcuts", "? or Ctrl+?")
        self.add_shortcut_row(app_group, "Quit Application", "Ctrl+Q")
        
        # Add key controller for Escape key
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
    
    def add_shortcut_row(self, group, action, shortcut):
        """Add a row with action and shortcut."""
        row = Adw.ActionRow()
        row.set_title(action)
        
        # Shortcut label
        shortcut_label = Gtk.Label(label=shortcut)
        shortcut_label.add_css_class("keycap")
        shortcut_label.add_css_class("monospace")
        shortcut_label.set_halign(Gtk.Align.END)
        row.add_suffix(shortcut_label)
        
        group.add(row)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape: close the window
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True  # Event handled
        
        return False  # Let other handlers process
