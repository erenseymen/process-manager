#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Process Manager - A modern Linux process manager

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk
from .window import ProcessManagerWindow
from .settings import Settings

APP_ID = "io.github.processmanager.ProcessManager"

# Application CSS styles
APP_CSS = """
.high-usage-panel {
    background-color: alpha(@warning_color, 0.1);
}

.high-usage-chip {
    padding: 4px 10px;
    border-radius: 16px;
    background-color: alpha(@warning_color, 0.15);
    border: 1px solid alpha(@warning_color, 0.3);
}

.high-usage-chip.high-cpu {
    background-color: alpha(@error_color, 0.15);
    border-color: alpha(@error_color, 0.3);
}

.high-usage-chip.high-mem {
    background-color: alpha(@warning_color, 0.15);
    border-color: alpha(@warning_color, 0.3);
}

.high-usage-chip .chip-name {
    font-weight: bold;
}

.high-usage-chip .chip-value {
    font-size: 0.9em;
    opacity: 0.85;
}

.selection-chip {
    padding: 4px 10px;
    border-radius: 16px;
    background-color: alpha(@accent_bg_color, 0.15);
    border: 1px solid alpha(@accent_color, 0.3);
}

.selection-chip .chip-name {
    font-weight: bold;
}

.selection-chip .chip-stats {
    font-size: 0.9em;
    opacity: 0.7;
}

.selection-chip .chip-remove {
    min-width: 20px;
    min-height: 20px;
    padding: 0;
}
"""


class ProcessManagerApplication(Adw.Application):
    """Main application class with single-instance support."""
    
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        
        self.settings = Settings()
        self.window = None
        
        # Set up actions
        self.create_actions()
        
        # Load CSS
        self.load_css()
    
    def create_actions(self):
        """Create application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        
        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)
        
        # Preferences action
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_preferences)
        self.add_action(preferences_action)
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
        
        # Refresh action (F5 still works)
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self.on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])
    
    def load_css(self):
        """Load application CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(APP_CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def do_activate(self):
        """Handle application activation (single instance)."""
        if not self.window:
            self.window = ProcessManagerWindow(application=self)
        
        self.window.present()
    
    def on_quit(self, action, param):
        """Quit the application."""
        self.quit()
    
    def on_about(self, action, param):
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="Process Manager",
            application_icon=APP_ID,
            developer_name="Process Manager Developers",
            version="1.0.0",
            developers=["Process Manager Contributors"],
            copyright="© 2024 Process Manager Developers",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/processmanager/processmanager",
            issue_url="https://github.com/processmanager/processmanager/issues"
        )
        about.present()
    
    def on_preferences(self, action, param):
        """Show preferences dialog."""
        from .preferences import PreferencesDialog
        dialog = PreferencesDialog(self.window, self.settings)
        dialog.present()
    
    def on_refresh(self, action, param):
        """Refresh process list."""
        if self.window:
            self.window.refresh_processes()


def main(version=None):
    """Main entry point."""
    app = ProcessManagerApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

