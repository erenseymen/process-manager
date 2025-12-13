# SPDX-License-Identifier: GPL-3.0-or-later
# Keyboard handler mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gdk


class KeyboardHandlerMixin:
    """Mixin class providing keyboard handling for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - view_stack: Adw.ViewStack
    - auto_refresh_button: Gtk.ToggleButton
    - selected_pids: dict
    - search_bar: Gtk.SearchBar
    - search_entry: Gtk.SearchEntry
    - current_tab: str
    - terminate_selected_processes: method
    - force_kill_selected_processes: method
    - show_selected_process_details: method
    - show_shortcuts: method
    - on_clear_selection: method
    - _get_current_tree_view_info: method
    - refresh_processes: method
    - refresh_gpu_processes: method
    - refresh_ports: method
    """
    
    def on_tree_view_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press in tree view - intercept shortcuts before TreeView handles them."""
        has_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        has_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        
        # Get current tree view
        tree_view, _, _ = self._get_current_tree_view_info()
        if not tree_view:
            return False
        
        # Handle Ctrl+TAB for tab switching
        if keyval == Gdk.KEY_Tab and has_ctrl and not has_alt and not has_shift:
            current_name = self.view_stack.get_visible_child_name()
            if current_name == "processes":
                self.view_stack.set_visible_child_name("gpu")
            elif current_name == "gpu":
                self.view_stack.set_visible_child_name("ports")
            else:
                self.view_stack.set_visible_child_name("processes")
            return True  # Event handled, don't let TreeView process it
        
        # Handle Space - toggle Play/Pause auto refresh
        if keyval == Gdk.KEY_space and not has_ctrl and not has_alt and not has_shift:
            self.auto_refresh_button.set_active(not self.auto_refresh_button.get_active())
            return True  # Event handled, don't let TreeView process it
        
        # Handle Delete - terminate selected processes (SIGTERM)
        if keyval == Gdk.KEY_Delete and not has_shift and not has_ctrl and not has_alt:
            if self.selected_pids:
                self.terminate_selected_processes()
                return True  # Event handled
            return False
        
        # Handle Shift+Delete - force kill selected processes (SIGKILL)
        if keyval == Gdk.KEY_Delete and has_shift and not has_ctrl and not has_alt:
            if self.selected_pids:
                self.force_kill_selected_processes()
                return True  # Event handled
            return False
        
        # Handle Enter - show process details dialog
        if (keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter) and not has_ctrl and not has_alt and not has_shift:
            self.show_selected_process_details()
            return True  # Event handled
        
        return False  # Let TreeView handle other keys
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press for global shortcuts and search."""
        # Check modifier keys
        has_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        has_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        
        # Handle Ctrl+TAB for tab switching
        if keyval == Gdk.KEY_Tab and has_ctrl and not has_alt and not has_shift:
            current_name = self.view_stack.get_visible_child_name()
            if current_name == "processes":
                self.view_stack.set_visible_child_name("gpu")
            elif current_name == "gpu":
                self.view_stack.set_visible_child_name("ports")
            else:
                self.view_stack.set_visible_child_name("processes")
            return True  # Event handled
        
        # Handle Ctrl+F - toggle filter/search bar
        if keyval == Gdk.KEY_f and has_ctrl and not has_alt and not has_shift:
            if self.search_bar.get_search_mode():
                # Close search bar
                self.search_entry.set_text("")
                self.search_bar.set_search_mode(False)
                # Focus current tab's tree view
                tree_view, _, _ = self._get_current_tree_view_info()
                tree_view.grab_focus()
            else:
                # Open search bar
                self.search_bar.set_search_mode(True)
                self.search_entry.grab_focus()
            return True  # Event handled
        
        # Handle Escape key to close search bar or clear selections
        if keyval == Gdk.KEY_Escape:
            if self.search_bar.get_search_mode():
                self.search_entry.set_text("")
                self.search_bar.set_search_mode(False)
                # Focus current tab's tree view
                tree_view, _, _ = self._get_current_tree_view_info()
                tree_view.grab_focus()
                return True  # Event handled
            elif self.selected_pids:
                # Search bar is closed, clear selections
                self.on_clear_selection(None)
                return True  # Event handled
            return False
        
        
        # Handle Space - toggle Play/Pause auto refresh
        if keyval == Gdk.KEY_space and not has_ctrl and not has_alt and not has_shift:
            # Don't handle if search bar is focused
            if self.search_bar.get_search_mode() and self.search_entry.has_focus():
                return False
            # Toggle auto refresh
            self.auto_refresh_button.set_active(not self.auto_refresh_button.get_active())
            return True  # Event handled
        
        # Handle Delete - terminate selected processes (SIGTERM)
        if keyval == Gdk.KEY_Delete and not has_shift and not has_ctrl and not has_alt:
            if self.selected_pids:
                self.terminate_selected_processes()
                return True  # Event handled
            return False
        
        # Handle Shift+Delete - force kill selected processes (SIGKILL)
        if keyval == Gdk.KEY_Delete and has_shift and not has_ctrl and not has_alt:
            if self.selected_pids:
                self.force_kill_selected_processes()
                return True  # Event handled
            return False
        
        # If search bar is visible and focused, let it handle keys
        if self.search_bar.get_search_mode() and self.search_entry.has_focus():
            return False
        
        # Get the character from keyval
        char = chr(keyval) if 32 <= keyval <= 126 else None
        
        # Handle ? key - show keyboard shortcuts (before opening search bar)
        if char == '?':
            self.show_shortcuts()
            return True  # Event handled
        
        # Check if it's a printable character (letter, number, etc.)
        if char and char.isprintable():
            # Open search bar
            self.search_bar.set_search_mode(True)
            # Focus search entry
            self.search_entry.grab_focus()
            # Append to existing text or set new text
            current_text = self.search_entry.get_text()
            self.search_entry.set_text(current_text + char)
            # Move cursor to end
            self.search_entry.set_position(-1)
            return True  # Event handled
        
        return False  # Let other handlers process
    
    def on_search_changed(self, entry):
        """Handle search text change."""
        if self.current_tab == 'gpu':
            self.refresh_gpu_processes()
        elif self.current_tab == 'ports':
            self.refresh_ports()
        else:
            self.refresh_processes()
    
    def on_search_activate(self, entry):
        """Handle Enter key in search - select all visible (filtered) processes."""
        search_text = entry.get_text().strip()
        if not search_text:
            return
        
        # Get current tab's tree view and list store
        tree_view, list_store, _ = self._get_current_tree_view_info()
        
        # Select all currently visible processes (they are already filtered by search)
        selection = tree_view.get_selection()
        for i in range(len(list_store)):
            selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        # Clear search and close search bar
        entry.set_text("")
        self.search_bar.set_search_mode(False)
        
        # Focus back to tree view
        tree_view.grab_focus()
