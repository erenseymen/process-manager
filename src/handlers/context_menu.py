# SPDX-License-Identifier: GPL-3.0-or-later
# Context menu mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import signal
from gi.repository import Gtk, Gdk, Gio


class ContextMenuMixin:
    """Mixin class providing context menu functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - settings: Settings instance
    - tree_view: Gtk.TreeView
    - selected_pids: dict
    - _get_current_tree_view_info: method
    - toggle_bookmark: method
    - on_change_priority: method
    - on_kill_process: method
    - force_kill_selected_processes: method
    - process_manager: ProcessManager instance
    - toast_overlay: Adw.ToastOverlay
    - _refresh_current_tab: method
    """
    
    def on_right_click(self, gesture, n_press, x, y):
        """Handle right-click context menu for processes tab."""
        self._handle_right_click(self.tree_view, x, y)
    
    def _handle_right_click(self, tree_view, x, y):
        """Common handler for right-click context menu."""
        # Get clicked row
        path_info = tree_view.get_path_at_pos(int(x), int(y))
        if path_info:
            path, column, cell_x, cell_y = path_info
            selection = tree_view.get_selection()
            
            if not selection.path_is_selected(path):
                selection.unselect_all()
                selection.select_path(path)
            
            # Show context menu
            self._show_context_menu(tree_view, x, y)
    
    def _show_context_menu(self, tree_view, x, y):
        """Show the process context menu."""
        # Get selected PID
        selection = tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            return
        
        path = paths[0]
        iter = model.get_iter(path)
        tree_view, _, pid_col = self._get_current_tree_view_info()
        pid = model.get_value(iter, pid_col)
        
        # Create a simple popover menu
        popover = Gtk.PopoverMenu()
        popover.set_parent(tree_view)
        
        # Create menu model
        menu = Gio.Menu()
        
        # Bookmark/Unbookmark action
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        is_bookmarked = pid in bookmarked_pids
        bookmark_action = Gio.SimpleAction.new("context-bookmark", None)
        bookmark_action.connect("activate", lambda a, p: self.toggle_bookmark(pid))
        self.add_action(bookmark_action)
        menu.append("Unbookmark Process" if is_bookmarked else "Bookmark Process", "win.context-bookmark")
        
        menu.append("_", None)  # Separator
        
        # Change Priority action
        priority_action = Gio.SimpleAction.new("context-priority", None)
        priority_action.connect("activate", lambda a, p: self.on_change_priority(None))
        self.add_action(priority_action)
        menu.append("Change Priority...", "win.context-priority")
        
        # Signals submenu
        signals_menu = Gio.Menu()
        
        # Stop action (SIGSTOP)
        stop_action = Gio.SimpleAction.new("context-stop", None)
        stop_action.connect("activate", lambda a, p: self.send_signal_to_selected(signal.SIGSTOP))
        self.add_action(stop_action)
        signals_menu.append("Stop (SIGSTOP)", "win.context-stop")
        
        # Continue action (SIGCONT)
        cont_action = Gio.SimpleAction.new("context-cont", None)
        cont_action.connect("activate", lambda a, p: self.send_signal_to_selected(signal.SIGCONT))
        self.add_action(cont_action)
        signals_menu.append("Continue (SIGCONT)", "win.context-cont")
        
        # Hangup action (SIGHUP)
        hup_action = Gio.SimpleAction.new("context-hup", None)
        hup_action.connect("activate", lambda a, p: self.send_signal_to_selected(signal.SIGHUP))
        self.add_action(hup_action)
        signals_menu.append("Hangup (SIGHUP)", "win.context-hup")
        
        # Interrupt action (SIGINT)
        int_action = Gio.SimpleAction.new("context-int", None)
        int_action.connect("activate", lambda a, p: self.send_signal_to_selected(signal.SIGINT))
        self.add_action(int_action)
        signals_menu.append("Interrupt (SIGINT)", "win.context-int")
        
        menu.append_submenu("Send Signal", signals_menu)
        
        menu.append("_", None)  # Separator
        
        # End Process action
        end_action = Gio.SimpleAction.new("context-kill", None)
        end_action.connect("activate", lambda a, p: self.on_kill_process(None))
        self.add_action(end_action)
        menu.append("End Process (SIGTERM)", "win.context-kill")
        
        # Force Kill action
        force_kill_action = Gio.SimpleAction.new("context-force-kill", None)
        force_kill_action.connect("activate", lambda a, p: self.force_kill_selected_processes())
        self.add_action(force_kill_action)
        menu.append("Force Kill (SIGKILL)", "win.context-force-kill")
        
        popover.set_menu_model(menu)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()
