#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Process Manager - A modern Linux process manager

"""Main application module for Process Manager."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, Gdk

from .constants import APP_ID, APP_NAME, APP_VERSION, APP_WEBSITE, APP_ISSUE_URL
from .window import ProcessManagerWindow
from .settings import Settings

if TYPE_CHECKING:
    from gi.repository import GLib


class ProcessManagerApplication(Adw.Application):
    """Main application class with single-instance support."""
    
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        
        self.settings = Settings()
        self.window: Optional[ProcessManagerWindow] = None
        
        # Set up actions
        self._create_actions()
        
        # Load CSS
        self._load_css()
    
    def _create_actions(self) -> None:
        """Create application actions and keyboard shortcuts."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        
        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)
        
        # Preferences action
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self._on_preferences)
        self.add_action(preferences_action)
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
        
        # Refresh action
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])
        
        # Keyboard shortcuts action
        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self._on_shortcuts)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["<Control>question"])
    
    def _load_css(self) -> None:
        """Load application CSS styles from external file."""
        import os
        from pathlib import Path
        
        css_provider = Gtk.CssProvider()
        
        # Try multiple locations for CSS file
        css_paths = [
            # Development: relative to source
            Path(__file__).parent.parent / 'data' / 'style.css',
            # Installed: in pkgdatadir
            Path('/app/share/process-manager/style.css'),  # Flatpak
            Path('/usr/share/process-manager/style.css'),  # System install
            Path('/usr/local/share/process-manager/style.css'),  # Local install
        ]
        
        for css_path in css_paths:
            if css_path.exists():
                css_provider.load_from_path(str(css_path))
                break
        else:
            # Fallback: load inline CSS if file not found
            from .constants import APP_CSS
            css_provider.load_from_data(APP_CSS.encode())
        
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def do_activate(self) -> None:
        """Handle application activation (single instance)."""
        if not self.window:
            self.window = ProcessManagerWindow(application=self)
        
        self.window.present()
    
    def _on_quit(self, action: Gio.SimpleAction, param: None) -> None:
        """Quit the application."""
        self.quit()
    
    def _on_about(self, action: Gio.SimpleAction, param: None) -> None:
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name=APP_NAME,
            application_icon=APP_ID,
            developer_name="Process Manager Developers",
            version=APP_VERSION,
            developers=["Process Manager Contributors"],
            copyright="© 2024 Process Manager Developers",
            license_type=Gtk.License.GPL_3_0,
            website=APP_WEBSITE,
            issue_url=APP_ISSUE_URL
        )
        about.present()
    
    def _on_preferences(self, action: Gio.SimpleAction, param: None) -> None:
        """Show preferences dialog."""
        from .preferences import PreferencesDialog
        dialog = PreferencesDialog(self.window, self.settings)
        dialog.present()
    
    def _on_refresh(self, action: Gio.SimpleAction, param: None) -> None:
        """Refresh process list."""
        if self.window:
            self.window.refresh_processes()
    
    def _on_shortcuts(self, action: Gio.SimpleAction, param: None) -> None:
        """Show keyboard shortcuts window."""
        if self.window:
            self.window.show_shortcuts()


def main(version: Optional[str] = None) -> int:
    """Main entry point for the application.
    
    Args:
        version: Optional version string (unused, kept for compatibility).
        
    Returns:
        Exit code from the application.
    """
    app = ProcessManagerApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

