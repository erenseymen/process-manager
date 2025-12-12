#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Process Manager - A modern Linux process manager

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib
from .window import ProcessManagerWindow
from .settings import Settings

APP_ID = "io.github.processmanager.ProcessManager"


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
        
        # Refresh action (F5 still works)
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self.on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])
    
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

