# SPDX-License-Identifier: GPL-3.0-or-later
# Main window

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import os
import signal
from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk
from .process_manager import ProcessManager
from .system_stats import SystemStats


class TerminationDialog(Adw.Window):
    """Dialog for terminating processes with status tracking."""
    
    def __init__(self, parent, process_manager, processes):
        """
        Args:
            parent: Parent window
            process_manager: ProcessManager instance
            processes: List of dicts with 'pid' and 'name' keys
        """
        super().__init__(
            transient_for=parent,
            modal=True,
            title="End Processes",
            default_width=450,
            default_height=400,
        )
        
        self.parent_window = parent
        self.process_manager = process_manager
        self.processes = {p['pid']: {'name': p['name'], 'status': 'pending'} for p in processes}
        self.check_timeout_id = None
        self.confirmed = False
        
        self.build_ui()
    
    def build_ui(self):
        """Build the dialog UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Content box with margins
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        main_box.append(content_box)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0)
        self.update_status_label()
        content_box.append(self.status_label)
        
        # Process list in scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(150)
        
        self.process_list_box = Gtk.ListBox()
        self.process_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.process_list_box.add_css_class("boxed-list")
        scrolled.set_child(self.process_list_box)
        content_box.append(scrolled)
        
        # Build process rows
        self.process_rows = {}
        for pid, info in self.processes.items():
            row = self.create_process_row(pid, info['name'])
            self.process_rows[pid] = row
            self.process_list_box.append(row['row'])
        
        # Button box
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.button_box.set_halign(Gtk.Align.END)
        content_box.append(self.button_box)
        
        # Cancel button (shown initially)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", self.on_cancel)
        self.button_box.append(self.cancel_button)
        
        # Confirm button (shown initially)
        self.confirm_button = Gtk.Button(label="End Processes")
        self.confirm_button.add_css_class("destructive-action")
        self.confirm_button.connect("clicked", self.on_confirm)
        self.button_box.append(self.confirm_button)
        
        # Kill All button (hidden initially)
        self.kill_all_button = Gtk.Button(label="Force Kill All")
        self.kill_all_button.add_css_class("destructive-action")
        self.kill_all_button.connect("clicked", self.on_kill_all)
        self.kill_all_button.set_visible(False)
        self.button_box.append(self.kill_all_button)
        
        # Close button (hidden initially)
        self.close_button = Gtk.Button(label="Close")
        self.close_button.connect("clicked", self.on_close)
        self.close_button.set_visible(False)
        self.button_box.append(self.close_button)
        
        # Connect close request
        self.connect("close-request", self.on_close_request)
        
        # Add key controller for keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
    
    def create_process_row(self, pid, name):
        """Create a row for a process in the list."""
        row = Adw.ActionRow()
        row.set_title(name)
        row.set_subtitle(f"PID: {pid}")
        
        # Status icon
        status_icon = Gtk.Image()
        status_icon.set_from_icon_name("content-loading-symbolic")
        row.add_prefix(status_icon)
        
        # Kill button (hidden initially)
        kill_button = Gtk.Button()
        kill_button.set_icon_name("process-stop-symbolic")
        kill_button.set_tooltip_text("Force Kill (SIGKILL)")
        kill_button.add_css_class("destructive-action")
        kill_button.set_valign(Gtk.Align.CENTER)
        kill_button.connect("clicked", lambda b: self.on_kill_single(pid))
        kill_button.set_visible(False)
        row.add_suffix(kill_button)
        
        return {
            'row': row,
            'status_icon': status_icon,
            'kill_button': kill_button
        }
    
    def update_status_label(self):
        """Update the status label text."""
        if not self.confirmed:
            count = len(self.processes)
            self.status_label.set_markup(
                f"<b>Are you sure you want to end {count} process(es)?</b>\n"
                "Unsaved data may be lost."
            )
        else:
            terminated = sum(1 for p in self.processes.values() if p['status'] == 'terminated')
            running = sum(1 for p in self.processes.values() if p['status'] == 'running')
            total = len(self.processes)
            
            if running == 0:
                self.status_label.set_markup(
                    f"<b>All {total} process(es) have been terminated.</b>"
                )
            else:
                self.status_label.set_markup(
                    f"<b>Terminated: {terminated}/{total}</b>\n"
                    f"{running} process(es) still running."
                )
    
    def update_process_row(self, pid, status):
        """Update the visual state of a process row."""
        if pid not in self.process_rows:
            return
        
        row_data = self.process_rows[pid]
        
        if status == 'terminated':
            row_data['status_icon'].set_from_icon_name("emblem-ok-symbolic")
            row_data['status_icon'].add_css_class("success")
            row_data['kill_button'].set_visible(False)
            row_data['row'].set_subtitle(f"PID: {pid} - Terminated")
        elif status == 'running':
            row_data['status_icon'].set_from_icon_name("dialog-warning-symbolic")
            row_data['status_icon'].add_css_class("warning")
            row_data['kill_button'].set_visible(True)
            row_data['row'].set_subtitle(f"PID: {pid} - Still running")
        elif status == 'pending':
            row_data['status_icon'].set_from_icon_name("content-loading-symbolic")
            row_data['kill_button'].set_visible(False)
    
    def on_cancel(self, button):
        """Handle cancel button click."""
        self.cleanup_and_close()
    
    def on_confirm(self, button):
        """Handle confirm button click - send SIGTERM to all processes."""
        self.confirmed = True
        
        # Hide confirmation buttons
        self.cancel_button.set_visible(False)
        self.confirm_button.set_visible(False)
        
        # Show close button
        self.close_button.set_visible(True)
        
        # Send SIGTERM to all processes
        for pid in self.processes:
            try:
                self.process_manager.kill_process(pid, signal.SIGTERM)
                self.processes[pid]['status'] = 'running'  # Will be checked
            except Exception:
                pass  # Process might already be gone
        
        # Start checking process status
        self.start_status_check()
    
    def start_status_check(self):
        """Start periodic check of process status."""
        self.check_processes_status()
        self.check_timeout_id = GLib.timeout_add(500, self.check_processes_status)
    
    def check_processes_status(self):
        """Check if processes are still running."""
        all_terminated = True
        any_running = False
        
        for pid in self.processes:
            if self.processes[pid]['status'] == 'terminated':
                continue
            
            # Check if process is still running
            if self.is_process_running(pid):
                self.processes[pid]['status'] = 'running'
                self.update_process_row(pid, 'running')
                all_terminated = False
                any_running = True
            else:
                self.processes[pid]['status'] = 'terminated'
                self.update_process_row(pid, 'terminated')
        
        # Update status label
        self.update_status_label()
        
        # Show/hide kill all button
        self.kill_all_button.set_visible(any_running)
        
        # If all terminated, stop checking
        if all_terminated:
            self.stop_status_check()
            return False
        
        return True  # Continue checking
    
    def is_process_running(self, pid):
        """Check if a process is still running."""
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            return True
    
    def on_kill_single(self, pid):
        """Handle kill button for a single process."""
        try:
            self.process_manager.kill_process(pid, signal.SIGKILL)
        except Exception:
            pass
        
        # Immediately check status
        GLib.timeout_add(100, self.check_processes_status)
    
    def on_kill_all(self, button):
        """Handle kill all button - send SIGKILL to all running processes."""
        for pid, info in self.processes.items():
            if info['status'] == 'running':
                try:
                    self.process_manager.kill_process(pid, signal.SIGKILL)
                except Exception:
                    pass
        
        # Immediately check status
        GLib.timeout_add(100, self.check_processes_status)
    
    def on_close(self, button):
        """Handle close button click."""
        self.cleanup_and_close()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape: close/cancel the dialog
        if keyval == Gdk.KEY_Escape:
            self.cleanup_and_close()
            return True  # Event handled
        
        # Enter: confirm or close
        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            if not self.confirmed:
                # Not confirmed yet - trigger confirmation
                self.on_confirm(self.confirm_button)
            elif self.close_button.get_visible():
                # Already confirmed and close button is visible - close the dialog
                self.on_close(self.close_button)
            return True  # Event handled
        
        return False  # Let other handlers process
    
    def on_close_request(self, window):
        """Handle window close request."""
        self.cleanup_and_close()
        return False
    
    def stop_status_check(self):
        """Stop the status check timer."""
        if self.check_timeout_id:
            GLib.source_remove(self.check_timeout_id)
            self.check_timeout_id = None
    
    def cleanup_and_close(self):
        """Clean up and close the dialog."""
        self.stop_status_check()
        self.close()
        
        # Remove terminated processes from parent's persistent selection
        if self.parent_window:
            for pid, info in self.processes.items():
                if info['status'] == 'terminated' and pid in self.parent_window.selected_pids:
                    del self.parent_window.selected_pids[pid]
            GLib.timeout_add(100, self.parent_window.refresh_processes)


class ProcessManagerWindow(Adw.ApplicationWindow):
    """Main application window."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        app = self.get_application()
        self.settings = app.settings
        self.process_manager = ProcessManager()
        self.system_stats = SystemStats()
        
        # Persistent selection tracking
        # Key: PID, Value: dict with process info (name, user, etc.)
        self.selected_pids = {}
        self._updating_selection = False  # Flag to prevent recursive selection updates
        
        # Cache for previous process stats (for change detection)
        # Key: PID, Value: dict with cpu, memory values
        self._prev_process_stats = {}
        
        # Window setup
        self.set_title("Process Manager")
        self.set_default_size(
            self.settings.get("window_width"),
            self.settings.get("window_height")
        )
        
        # Build UI
        self.build_ui()
        
        # Start refresh timer
        self.refresh_timeout_id = None
        self.start_refresh_timer()
        
        # Initial load
        self.refresh_processes()
        self.update_system_stats()
        
        # Connect window close to cleanup
        self.connect("close-request", self.on_close_request)
    
    def build_ui(self):
        """Build the user interface."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        
        # Auto Refresh Play/Pause toggle button (first in title)
        self.auto_refresh_button = Gtk.ToggleButton()
        # Restore saved auto refresh state (default: True)
        auto_refresh = self.settings.get("auto_refresh", True)
        self.auto_refresh_button.set_active(auto_refresh)
        self.auto_refresh_button.set_icon_name("media-playback-pause-symbolic" if auto_refresh else "media-playback-start-symbolic")
        self.auto_refresh_button.set_tooltip_text("Pause Auto Refresh" if auto_refresh else "Start Auto Refresh")
        self.auto_refresh_button.connect("toggled", self.on_auto_refresh_toggled)
        header.pack_start(self.auto_refresh_button)
        
        # All/User toggle button
        self.all_user_button = Gtk.ToggleButton()
        # Restore saved toggle state
        show_all = self.settings.get("show_all_toggle", True)
        self.all_user_button.set_active(show_all)
        self.all_user_button.set_label("All" if show_all else "User")
        self.all_user_button.connect("toggled", self.on_all_user_toggled)
        header.pack_start(self.all_user_button)
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self.create_menu())
        header.pack_end(menu_button)
        
        main_box.append(header)
        
        # Search bar (hidden by default, shown when typing)
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activate)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_search_mode(False)  # Hidden by default
        main_box.append(self.search_bar)
        
        # Key controller for typing to trigger search
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        # Selection panel (above process list)
        self.selection_panel = self.create_selection_panel()
        main_box.append(self.selection_panel)
        
        # Process list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.process_view = self.create_process_view()
        scrolled.set_child(self.process_view)
        main_box.append(scrolled)
        
        # High usage processes panel (above stats bar)
        self.high_usage_panel = self.create_high_usage_panel()
        main_box.append(self.high_usage_panel)
        
        # System stats bar
        self.stats_bar = self.create_stats_bar()
        main_box.append(self.stats_bar)
    
    def create_menu(self):
        """Create the application menu."""
        menu = Gio.Menu()
        
        menu.append("Preferences", "app.preferences")
        menu.append("About Process Manager", "app.about")
        menu.append("Quit", "app.quit")
        
        return menu
    
    def on_all_user_toggled(self, button):
        """Handle All/User toggle button."""
        if button.get_active():
            button.set_label("All")
        else:
            button.set_label("User")
        # Save the toggle state
        self.settings.set("show_all_toggle", button.get_active())
        self.refresh_processes()
    
    def on_auto_refresh_toggled(self, button):
        """Handle Refresh Auto toggle button."""
        auto_refresh = button.get_active()
        # Save the toggle state
        self.settings.set("auto_refresh", auto_refresh)
        
        # Update icon and tooltip
        if auto_refresh:
            button.set_icon_name("media-playback-pause-symbolic")
            button.set_tooltip_text("Pause Auto Refresh")
            # Start the timer if not already running
            if not self.refresh_timeout_id:
                self.start_refresh_timer()
        else:
            button.set_icon_name("media-playback-start-symbolic")
            button.set_tooltip_text("Start Auto Refresh")
            # Stop the timer
            if self.refresh_timeout_id:
                GLib.source_remove(self.refresh_timeout_id)
                self.refresh_timeout_id = None
    
    # Map column names to column IDs for sort persistence
    COLUMN_NAME_TO_ID = {
        "name": 0,
        "cpu": 1,
        "memory": 2,
        "started": 3,
        "user": 4,
        "nice": 5,
        "pid": 6,
    }
    COLUMN_ID_TO_NAME = {v: k for k, v in COLUMN_NAME_TO_ID.items()}
    
    def create_process_view(self):
        """Create the process list view."""
        # Create list store: name, cpu, memory, started, user, nice, pid
        self.list_store = Gtk.ListStore(str, str, str, str, str, str, int)
        
        # Create tree view
        tree_view = Gtk.TreeView(model=self.list_store)
        tree_view.set_headers_clickable(True)
        tree_view.set_enable_search(False)
        
        # Selection
        selection = tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self.on_selection_changed)
        
        # Right-click context menu
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self.on_right_click)
        tree_view.add_controller(gesture)
        
        # Key controller for tree view to handle Space key
        tree_key_controller = Gtk.EventControllerKey()
        tree_key_controller.connect("key-pressed", self.on_tree_view_key_pressed)
        tree_view.add_controller(tree_key_controller)
        
        # Columns
        columns = [
            ("Process Name", 0, 250),
            ("CPU %", 1, 80),
            ("Memory", 2, 100),
            ("Started", 3, 120),
            ("User", 4, 100),
            ("Nice", 5, 60),
            ("PID", 6, 80),
        ]
        
        for i, (title, col_id, width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if col_id == 0:  # Process name - ellipsize
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_min_width(60)
            column.set_fixed_width(width)
            column.set_sort_column_id(col_id)
            column.set_clickable(True)
            
            tree_view.append_column(column)
        
        # Custom sorting for numeric columns
        self.list_store.set_sort_func(1, self.sort_percent, None)  # CPU
        self.list_store.set_sort_func(2, self.sort_memory, None)   # Memory
        self.list_store.set_sort_func(3, self.sort_started, None)  # Started
        self.list_store.set_sort_func(5, self.sort_nice, None)     # Nice
        self.list_store.set_sort_func(6, self.sort_pid, None)      # PID
        
        # Restore saved sort column and order
        saved_column = self.settings.get("sort_column")
        saved_descending = self.settings.get("sort_descending")
        sort_col_id = self.COLUMN_NAME_TO_ID.get(saved_column, 1)  # Default to CPU
        sort_order = Gtk.SortType.DESCENDING if saved_descending else Gtk.SortType.ASCENDING
        self.list_store.set_sort_column_id(sort_col_id, sort_order)
        
        # Connect to sort changes to save them
        self.list_store.connect("sort-column-changed", self.on_sort_column_changed)
        
        self.tree_view = tree_view
        return tree_view
    
    def on_sort_column_changed(self, model):
        """Handle sort column change - save to settings."""
        sort_col_id, sort_order = model.get_sort_column_id()
        if sort_col_id is not None and sort_col_id >= 0:
            col_name = self.COLUMN_ID_TO_NAME.get(sort_col_id, "cpu")
            self.settings.set("sort_column", col_name)
            self.settings.set("sort_descending", sort_order == Gtk.SortType.DESCENDING)
    
    def sort_percent(self, model, iter1, iter2, user_data):
        """Sort by percentage value (reversed: highest first on initial click)."""
        val1 = model.get_value(iter1, 1).rstrip('%')
        val2 = model.get_value(iter2, 1).rstrip('%')
        try:
            # Reversed for descending on first click
            return (float(val2) > float(val1)) - (float(val2) < float(val1))
        except ValueError:
            return 0
    
    def sort_memory(self, model, iter1, iter2, user_data):
        """Sort by memory value (reversed: highest first on initial click)."""
        def parse_mem(s):
            s = s.strip()
            if s.endswith('GiB'):
                return float(s[:-3]) * 1024 * 1024
            elif s.endswith('MiB'):
                return float(s[:-3]) * 1024
            elif s.endswith('KiB'):
                return float(s[:-3])
            elif s.endswith('B'):
                return float(s[:-1]) / 1024
            return 0
        
        val1 = parse_mem(model.get_value(iter1, 2))
        val2 = parse_mem(model.get_value(iter2, 2))
        # Reversed for descending on first click
        return (val2 > val1) - (val2 < val1)
    
    def sort_started(self, model, iter1, iter2, user_data):
        """Sort by started time (reversed: newest first on initial click)."""
        val1 = model.get_value(iter1, 3)
        val2 = model.get_value(iter2, 3)
        # Reversed for descending on first click (newest/latest time first)
        return (val2 > val1) - (val2 < val1)
    
    def sort_nice(self, model, iter1, iter2, user_data):
        """Sort by nice value (column 5)."""
        try:
            val1 = int(model.get_value(iter1, 5))
            val2 = int(model.get_value(iter2, 5))
        except ValueError:
            return 0
        return (val1 > val2) - (val1 < val2)
    
    def sort_pid(self, model, iter1, iter2, user_data):
        """Sort by PID value (column 6)."""
        val1 = model.get_value(iter1, 6)
        val2 = model.get_value(iter2, 6)
        return (val1 > val2) - (val1 < val2)
    
    def create_selection_panel(self):
        """Create the selection panel showing selected processes grouped by name with comparison bars."""
        # Main container
        panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel_box.add_css_class("selection-panel")
        
        # Header row with title and clear button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(8)
        header_box.set_margin_top(6)
        header_box.set_margin_bottom(4)
        
        # Title label
        self.selection_title = Gtk.Label(label="Selected:")
        self.selection_title.add_css_class("heading")
        self.selection_title.set_halign(Gtk.Align.START)
        self.selection_title.set_hexpand(True)
        header_box.append(self.selection_title)
        
        # End Process button
        self.end_process_button = Gtk.Button()
        self.end_process_button.set_icon_name("process-stop-symbolic")
        self.end_process_button.set_tooltip_text("End Selected Processes")
        self.end_process_button.add_css_class("destructive-action")
        self.end_process_button.connect("clicked", self.on_kill_process)
        header_box.append(self.end_process_button)
        
        # Clear all button
        self.clear_button = Gtk.Button()
        self.clear_button.set_icon_name("edit-clear-all-symbolic")
        self.clear_button.set_tooltip_text("Clear Selection")
        self.clear_button.add_css_class("flat")
        self.clear_button.connect("clicked", self.on_clear_selection)
        header_box.append(self.clear_button)
        
        panel_box.append(header_box)
        
        # Scrolled window for process comparison list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(200)
        scrolled.set_propagate_natural_height(True)
        
        # ListBox for vertical process comparison
        self.selection_list = Gtk.ListBox()
        self.selection_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.selection_list.add_css_class("selection-comparison-list")
        self.selection_list.set_margin_start(12)
        self.selection_list.set_margin_end(12)
        self.selection_list.set_margin_bottom(8)
        scrolled.set_child(self.selection_list)
        panel_box.append(scrolled)
        
        # Bottom separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        panel_box.append(sep)
        
        # Initially hidden
        panel_box.set_visible(False)
        
        return panel_box
    
    def parse_cpu_str(self, cpu_str):
        """Parse CPU string like '5.2%' to float."""
        try:
            return float(cpu_str.rstrip('%'))
        except (ValueError, AttributeError):
            return 0.0
    
    def parse_mem_str(self, mem_str):
        """Parse memory string like '150.5 MiB' to bytes."""
        try:
            mem_str = mem_str.strip()
            if mem_str.endswith('GiB'):
                return float(mem_str[:-3].strip()) * 1024 * 1024 * 1024
            elif mem_str.endswith('MiB'):
                return float(mem_str[:-3].strip()) * 1024 * 1024
            elif mem_str.endswith('KiB'):
                return float(mem_str[:-3].strip()) * 1024
            elif mem_str.endswith('B'):
                return float(mem_str[:-1].strip())
            return 0
        except (ValueError, AttributeError):
            return 0
    
    def update_selection_panel(self):
        """Update the selection panel with current selection grouped by process name with comparison bars."""
        count = len(self.selected_pids)
        
        # Show/hide panel based on selection
        self.selection_panel.set_visible(count > 0)
        
        if count == 0:
            return
        
        # Calculate totals
        total_cpu = sum(self.parse_cpu_str(info.get('cpu_str', '0%')) 
                       for info in self.selected_pids.values())
        total_mem = sum(self.parse_mem_str(info.get('mem_str', '0 B')) 
                       for info in self.selected_pids.values())
        
        # Update title with totals
        self.selection_title.set_label(
            f"Selected ({count}): CPU {total_cpu:.1f}% | Mem {self.format_memory(total_mem)}"
        )
        
        # Clear existing rows
        while True:
            child = self.selection_list.get_row_at_index(0)
            if child is None:
                break
            self.selection_list.remove(child)
        
        # Group processes by name
        groups = {}
        for pid, info in self.selected_pids.items():
            name = info.get('name', 'Unknown')
            if name not in groups:
                groups[name] = {'pids': [], 'cpu': 0.0, 'mem': 0}
            groups[name]['pids'].append(pid)
            groups[name]['cpu'] += self.parse_cpu_str(info.get('cpu_str', '0%'))
            groups[name]['mem'] += self.parse_mem_str(info.get('mem_str', '0 B'))
        
        # Find max values for relative bar scaling
        max_cpu = max((g['cpu'] for g in groups.values()), default=1.0) or 1.0
        max_mem = max((g['mem'] for g in groups.values()), default=1) or 1
        
        # Sort groups by memory usage (descending) for comparison
        sorted_groups = sorted(groups.items(), key=lambda x: x[1]['mem'], reverse=True)
        
        # Create comparison rows for each group
        for name, group_info in sorted_groups:
            pids = sorted(group_info['pids'])
            row = self.create_comparison_row(name, pids, group_info['cpu'], group_info['mem'], max_cpu, max_mem)
            self.selection_list.append(row)
    
    def create_comparison_row(self, name, pids, total_cpu, total_mem, max_cpu, max_mem):
        """Create a comparison row widget for a selected process group with memory/CPU bars."""
        # Main row container
        row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row_box.add_css_class("comparison-row")
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        
        # Header: Process name + count + remove button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Process name and count
        if len(pids) == 1:
            name_text = f"{name}"
            pid_text = f"PID: {pids[0]}"
        else:
            name_text = f"{name} ({len(pids)})"
            pid_text = f"PIDs: {', '.join(str(p) for p in pids[:3])}" + ("..." if len(pids) > 3 else "")
        
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name_box.set_hexpand(True)
        
        name_label = Gtk.Label(label=name_text)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("comparison-name")
        name_box.append(name_label)
        
        pid_label = Gtk.Label(label=pid_text)
        pid_label.set_ellipsize(Pango.EllipsizeMode.END)
        pid_label.set_halign(Gtk.Align.START)
        pid_label.add_css_class("comparison-pid")
        name_box.append(pid_label)
        
        header_box.append(name_box)
        
        # Remove button
        remove_btn = Gtk.Button()
        remove_btn.set_icon_name("window-close-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.add_css_class("circular")
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.set_tooltip_text("Remove from selection")
        remove_btn.connect("clicked", lambda b: self.remove_group_from_selection(pids))
        header_box.append(remove_btn)
        
        row_box.append(header_box)
        
        # Stats bars container
        bars_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bars_box.add_css_class("comparison-bars")
        
        # Memory bar (primary comparison)
        mem_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        mem_label = Gtk.Label(label="Mem")
        mem_label.add_css_class("bar-label")
        mem_label.set_width_chars(4)
        mem_label.set_xalign(0)
        mem_bar_box.append(mem_label)
        
        # Memory progress bar
        mem_fraction = (total_mem / max_mem) if max_mem > 0 else 0
        mem_bar = Gtk.ProgressBar()
        mem_bar.set_fraction(mem_fraction)
        mem_bar.set_hexpand(True)
        mem_bar.add_css_class("comparison-mem-bar")
        # Add color class based on absolute memory usage
        if total_mem > 1024 * 1024 * 1024:  # > 1 GiB
            mem_bar.add_css_class("bar-high")
        elif total_mem > 256 * 1024 * 1024:  # > 256 MiB
            mem_bar.add_css_class("bar-medium")
        else:
            mem_bar.add_css_class("bar-low")
        mem_bar_box.append(mem_bar)
        
        mem_value = Gtk.Label(label=self.format_memory(total_mem))
        mem_value.add_css_class("bar-value")
        mem_value.set_width_chars(10)
        mem_value.set_xalign(1)
        mem_bar_box.append(mem_value)
        
        bars_box.append(mem_bar_box)
        
        # CPU bar
        cpu_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        cpu_label = Gtk.Label(label="CPU")
        cpu_label.add_css_class("bar-label")
        cpu_label.set_width_chars(4)
        cpu_label.set_xalign(0)
        cpu_bar_box.append(cpu_label)
        
        # CPU progress bar
        cpu_fraction = (total_cpu / max_cpu) if max_cpu > 0 else 0
        cpu_bar = Gtk.ProgressBar()
        cpu_bar.set_fraction(cpu_fraction)
        cpu_bar.set_hexpand(True)
        cpu_bar.add_css_class("comparison-cpu-bar")
        # Add color class based on absolute CPU usage
        if total_cpu > 50:
            cpu_bar.add_css_class("bar-high")
        elif total_cpu > 10:
            cpu_bar.add_css_class("bar-medium")
        else:
            cpu_bar.add_css_class("bar-low")
        cpu_bar_box.append(cpu_bar)
        
        cpu_value = Gtk.Label(label=f"{total_cpu:.1f}%")
        cpu_value.add_css_class("bar-value")
        cpu_value.set_width_chars(10)
        cpu_value.set_xalign(1)
        cpu_bar_box.append(cpu_value)
        
        bars_box.append(cpu_bar_box)
        
        row_box.append(bars_box)
        
        return row_box
    
    def remove_group_from_selection(self, pids):
        """Remove a group of processes from selection."""
        for pid in pids:
            if pid in self.selected_pids:
                del self.selected_pids[pid]
        self.update_selection_panel()
        # Update tree view selection
        self._updating_selection = True
        selection = self.tree_view.get_selection()
        for pid in pids:
            for i, row in enumerate(self.list_store):
                if row[6] == pid:
                    selection.unselect_path(Gtk.TreePath.new_from_indices([i]))
                    break
        self._updating_selection = False
    
    def on_clear_selection(self, button):
        """Clear all selections."""
        self.selected_pids.clear()
        self.update_selection_panel()
        # Update tree view selection
        self._updating_selection = True
        self.tree_view.get_selection().unselect_all()
        self._updating_selection = False
        self.refresh_processes()
    
    def remove_from_selection(self, pid):
        """Remove a single process from selection."""
        if pid in self.selected_pids:
            del self.selected_pids[pid]
        self.update_selection_panel()
        # Update tree view selection
        self._updating_selection = True
        selection = self.tree_view.get_selection()
        for i, row in enumerate(self.list_store):
            if row[6] == pid:
                selection.unselect_path(Gtk.TreePath.new_from_indices([i]))
                break
        self._updating_selection = False
    
    def create_high_usage_panel(self):
        """Create the high usage processes panel shown above swap/memory stats."""
        # Main container
        panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel_box.add_css_class("high-usage-panel")
        
        # Top separator
        sep_top = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        panel_box.append(sep_top)
        
        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_top(8)
        content_box.set_margin_bottom(8)
        
        # Warning icon
        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.add_css_class("warning")
        content_box.append(warning_icon)
        
        # High usage processes flow box
        self.high_usage_flow = Gtk.FlowBox()
        self.high_usage_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.high_usage_flow.set_homogeneous(False)
        self.high_usage_flow.set_max_children_per_line(50)
        self.high_usage_flow.set_min_children_per_line(1)
        self.high_usage_flow.set_row_spacing(4)
        self.high_usage_flow.set_column_spacing(8)
        self.high_usage_flow.set_hexpand(True)
        content_box.append(self.high_usage_flow)
        
        panel_box.append(content_box)
        
        # Initially hidden
        panel_box.set_visible(False)
        
        return panel_box
    
    def update_high_usage_panel(self, processes):
        """Update the high usage panel with processes that changed significantly."""
        cpu_change_threshold = self.settings.get("cpu_change_threshold")
        mem_change_threshold = self.settings.get("memory_change_threshold")
        
        # Get total memory for percentage calculation
        stats = self.system_stats.get_memory_info()
        mem_total = stats['mem_total']
        
        # Find processes with significant changes
        changed_cpu = []
        changed_mem = []
        
        # Build current stats and detect changes
        current_stats = {}
        for proc in processes:
            pid = proc['pid']
            cpu_percent = proc['cpu']
            mem_percent = (proc['memory'] / mem_total * 100) if mem_total > 0 else 0
            
            current_stats[pid] = {
                'cpu': cpu_percent,
                'memory': mem_percent,
                'name': proc['name']
            }
            
            # Check for changes if we have previous data
            if pid in self._prev_process_stats:
                prev = self._prev_process_stats[pid]
                cpu_change = cpu_percent - prev['cpu']
                mem_change = mem_percent - prev['memory']
                
                # Check CPU change (absolute change >= threshold)
                if abs(cpu_change) >= cpu_change_threshold:
                    changed_cpu.append({
                        'pid': pid,
                        'name': proc['name'],
                        'value': cpu_percent,
                        'change': cpu_change,
                        'type': 'cpu'
                    })
                
                # Check memory change (absolute change >= threshold)
                if abs(mem_change) >= mem_change_threshold:
                    changed_mem.append({
                        'pid': pid,
                        'name': proc['name'],
                        'value': mem_percent,
                        'change': mem_change,
                        'type': 'mem'
                    })
        
        # Update previous stats cache
        self._prev_process_stats = current_stats
        
        # Sort by absolute change descending
        changed_cpu.sort(key=lambda x: abs(x['change']), reverse=True)
        changed_mem.sort(key=lambda x: abs(x['change']), reverse=True)
        
        # Clear existing items
        while True:
            child = self.high_usage_flow.get_child_at_index(0)
            if child is None:
                break
            self.high_usage_flow.remove(child)
        
        # Show/hide panel
        has_changes = len(changed_cpu) > 0 or len(changed_mem) > 0
        self.high_usage_panel.set_visible(has_changes)
        
        if not has_changes:
            return
        
        # Add CPU change processes
        for proc in changed_cpu[:5]:  # Limit to top 5
            chip = self.create_high_usage_chip(proc, 'cpu')
            self.high_usage_flow.append(chip)
        
        # Add memory change processes (avoid duplicates)
        changed_cpu_pids = {p['pid'] for p in changed_cpu[:5]}
        for proc in changed_mem[:5]:  # Limit to top 5
            if proc['pid'] not in changed_cpu_pids:
                chip = self.create_high_usage_chip(proc, 'mem')
                self.high_usage_flow.append(chip)
    
    def create_high_usage_chip(self, proc, usage_type):
        """Create a chip widget for a process with significant usage change."""
        chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chip_box.add_css_class("high-usage-chip")
        
        change = proc.get('change', 0)
        
        # Add class based on change direction and type
        if change > 0:
            chip_box.add_css_class("change-up")
        else:
            chip_box.add_css_class("change-down")
        
        if usage_type == 'cpu':
            chip_box.add_css_class("high-cpu")
        else:
            chip_box.add_css_class("high-mem")
        
        # Process name
        name_label = Gtk.Label(label=proc['name'])
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(15)
        name_label.add_css_class("chip-name")
        chip_box.append(name_label)
        
        # Change indicator with arrow
        arrow = "↑" if change > 0 else "↓"
        if usage_type == 'cpu':
            value_text = f"CPU {arrow}{abs(change):.1f}%"
        else:
            value_text = f"Mem {arrow}{abs(change):.1f}%"
        
        value_label = Gtk.Label(label=value_text)
        value_label.add_css_class("chip-value")
        chip_box.append(value_label)
        
        # Make clickable to select the process
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda g, n, x, y: self.select_process_by_pid(proc['pid']))
        chip_box.add_controller(gesture)
        
        return chip_box
    
    def select_process_by_pid(self, pid):
        """Select a process in the tree view by PID."""
        selection = self.tree_view.get_selection()
        for i, row in enumerate(self.list_store):
            if row[6] == pid:  # PID column
                selection.select_path(Gtk.TreePath.new_from_indices([i]))
                # Scroll to the selected row
                self.tree_view.scroll_to_cell(
                    Gtk.TreePath.new_from_indices([i]), 
                    None, True, 0.5, 0.0
                )
                break
    
    def create_stats_bar(self):
        """Create the system stats bar at the bottom."""
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        stats_box.set_margin_start(12)
        stats_box.set_margin_end(12)
        stats_box.set_margin_top(8)
        stats_box.set_margin_bottom(8)
        stats_box.add_css_class("stats-bar")
        
        # Memory section
        mem_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.mem_indicator = Gtk.DrawingArea()
        self.mem_indicator.set_size_request(24, 24)
        self.mem_indicator.set_draw_func(self.draw_memory_indicator)
        mem_box.append(self.mem_indicator)
        
        mem_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.mem_title = Gtk.Label(label="Memory")
        self.mem_title.add_css_class("heading")
        self.mem_title.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_title)
        
        self.mem_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.mem_details.add_css_class("dim-label")
        self.mem_details.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_details)
        
        self.mem_cache = Gtk.Label(label="Cache 0 B")
        self.mem_cache.add_css_class("dim-label")
        self.mem_cache.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_cache)
        
        mem_box.append(mem_label_box)
        stats_box.append(mem_box)
        
        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep)
        
        # Swap section
        swap_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.swap_indicator = Gtk.DrawingArea()
        self.swap_indicator.set_size_request(24, 24)
        self.swap_indicator.set_draw_func(self.draw_swap_indicator)
        swap_box.append(self.swap_indicator)
        
        swap_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.swap_title = Gtk.Label(label="Swap")
        self.swap_title.add_css_class("heading")
        self.swap_title.set_halign(Gtk.Align.START)
        swap_label_box.append(self.swap_title)
        
        self.swap_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.swap_details.add_css_class("dim-label")
        self.swap_details.set_halign(Gtk.Align.START)
        swap_label_box.append(self.swap_details)
        
        swap_box.append(swap_label_box)
        stats_box.append(swap_box)
        
        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep2)
        
        # Disk section
        disk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.disk_indicator = Gtk.DrawingArea()
        self.disk_indicator.set_size_request(24, 24)
        self.disk_indicator.set_draw_func(self.draw_disk_indicator)
        disk_box.append(self.disk_indicator)
        
        disk_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.disk_title = Gtk.Label(label="Disk")
        self.disk_title.add_css_class("heading")
        self.disk_title.set_halign(Gtk.Align.START)
        disk_label_box.append(self.disk_title)
        
        self.disk_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.disk_details.add_css_class("dim-label")
        self.disk_details.set_halign(Gtk.Align.START)
        disk_label_box.append(self.disk_details)
        
        disk_box.append(disk_label_box)
        stats_box.append(disk_box)
        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        stats_box.append(spacer)
        
        return stats_box
    
    def draw_memory_indicator(self, area, cr, width, height):
        """Draw circular memory usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.mem_percent, (0.8, 0.2, 0.2))
    
    def draw_swap_indicator(self, area, cr, width, height):
        """Draw circular swap usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.swap_percent, (0.2, 0.8, 0.2))
    
    def draw_disk_indicator(self, area, cr, width, height):
        """Draw circular disk usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.disk_percent, (0.2, 0.2, 0.8))
    
    def draw_circular_indicator(self, cr, width, height, percent, color):
        """Draw a circular progress indicator."""
        import math
        
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 2
        line_width = 3
        
        # Background circle
        cr.set_line_width(line_width)
        cr.set_source_rgba(0.3, 0.3, 0.3, 0.5)
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()
        
        # Progress arc
        if percent > 0:
            cr.set_source_rgba(*color, 1.0)
            start_angle = -math.pi / 2
            end_angle = start_angle + (2 * math.pi * percent / 100)
            cr.arc(center_x, center_y, radius, start_angle, end_angle)
            cr.stroke()
    
    # Initialize percent values
    mem_percent = 0
    swap_percent = 0
    disk_percent = 0
    
    def on_selection_changed(self, selection):
        """Handle selection changes - sync with persistent selected_pids."""
        if self._updating_selection:
            return
        
        model, paths = selection.get_selected_rows()
        
        # Get currently visible selected PIDs
        visible_selected = set()
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, 6)  # PID column
            name = model.get_value(iter, 0)
            cpu_str = model.get_value(iter, 1)  # e.g., "5.2%"
            mem_str = model.get_value(iter, 2)  # e.g., "150.5 MiB"
            user = model.get_value(iter, 4)
            visible_selected.add(pid)
            # Store process info for selected PIDs
            self.selected_pids[pid] = {
                'name': name,
                'user': user,
                'cpu_str': cpu_str,
                'mem_str': mem_str
            }
        
        # Get all visible PIDs
        visible_pids = set()
        for row in self.list_store:
            visible_pids.add(row[6])
        
        # Remove deselected PIDs (only those that are visible and not selected)
        pids_to_remove = []
        for pid in self.selected_pids:
            if pid in visible_pids and pid not in visible_selected:
                pids_to_remove.append(pid)
        
        for pid in pids_to_remove:
            del self.selected_pids[pid]
        
        # Update the selection panel
        self.update_selection_panel()
    
    def refresh_processes(self):
        """Refresh the process list."""
        # Get filter settings from All/User toggle
        show_all = self.all_user_button.get_active()
        my_processes = not show_all
        
        # Get kernel threads setting
        show_kernel_threads = self.settings.get("show_kernel_threads", False)
        
        # Get search text
        search_text = self.search_entry.get_text().lower()
        
        # Get all processes (to check if selected ones still exist)
        all_processes = self.process_manager.get_processes(
            show_all=True,
            my_processes=False,
            active_only=False,
            show_kernel_threads=True
        )
        all_pids = {p['pid'] for p in all_processes}
        all_process_map = {p['pid']: p for p in all_processes}
        
        # Clean up ended processes from selection and update info for existing ones
        pids_to_remove = [pid for pid in self.selected_pids if pid not in all_pids]
        for pid in pids_to_remove:
            del self.selected_pids[pid]
        
        # Update cpu/memory info for selected processes
        for pid in self.selected_pids:
            if pid in all_process_map:
                proc = all_process_map[pid]
                self.selected_pids[pid]['cpu_str'] = f"{proc['cpu']:.1f}%"
                self.selected_pids[pid]['mem_str'] = self.format_memory(proc['memory'])
        
        # Get filtered processes
        processes = self.process_manager.get_processes(
            show_all=show_all,
            my_processes=my_processes,
            active_only=False,
            show_kernel_threads=show_kernel_threads
        )
        
        # Filter by search
        if search_text:
            # When searching, hide already selected items from results
            filtered_processes = [p for p in processes if 
                        (search_text in p['name'].lower() or 
                         search_text in str(p['pid']) or
                         search_text in p['user'].lower()) and
                        p['pid'] not in self.selected_pids]
        else:
            filtered_processes = processes
            
            # Get PIDs of filtered processes
            filtered_pids = {p['pid'] for p in filtered_processes}
            
            # Add selected processes that don't match the filter but still exist
            # (only when not searching)
            for pid in self.selected_pids:
                if pid not in filtered_pids and pid in all_pids:
                    # Add selected process to the list
                    filtered_processes.append(all_process_map[pid])
        
        # Update list store
        self._updating_selection = True
        self.list_store.clear()
        for proc in filtered_processes:
            self.list_store.append([
                proc['name'],
                f"{proc['cpu']:.1f}%",
                self.format_memory(proc['memory']),
                proc['started'],
                proc['user'],
                str(proc['nice']),
                proc['pid']
            ])
        
        # Restore selection by PID from persistent selection
        selection = self.tree_view.get_selection()
        if self.selected_pids:
            for i, row in enumerate(self.list_store):
                if row[6] in self.selected_pids:  # PID column
                    selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        self._updating_selection = False
        
        # Update the selection panel (in case processes were cleaned up)
        self.update_selection_panel()
        
        # Update high usage panel
        self.update_high_usage_panel(all_processes)
    
    def format_memory(self, bytes_val):
        """Format memory in human-readable format."""
        if bytes_val >= 1024 ** 3:
            return f"{bytes_val / (1024 ** 3):.1f} GiB"
        elif bytes_val >= 1024 ** 2:
            return f"{bytes_val / (1024 ** 2):.1f} MiB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.1f} KiB"
        return f"{bytes_val} B"
    
    def update_system_stats(self):
        """Update system memory, swap, and disk stats."""
        stats = self.system_stats.get_memory_info()
        
        # Memory
        mem_used = stats['mem_used']
        mem_total = stats['mem_total']
        mem_cache = stats['mem_cache']
        self.mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
        
        self.mem_details.set_text(
            f"{self.format_memory(mem_used)} ({self.mem_percent:.1f}%) of {self.format_memory(mem_total)}"
        )
        self.mem_cache.set_text(f"Cache {self.format_memory(mem_cache)}")
        self.mem_indicator.queue_draw()
        
        # Swap
        swap_used = stats['swap_used']
        swap_total = stats['swap_total']
        self.swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0
        
        self.swap_details.set_text(
            f"{self.format_memory(swap_used)} ({self.swap_percent:.1f}%) of {self.format_memory(swap_total)}"
        )
        self.swap_indicator.queue_draw()
        
        # Disk
        disk_stats = self.system_stats.get_disk_info()
        disk_used = disk_stats['disk_used']
        disk_total = disk_stats['disk_total']
        self.disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
        
        self.disk_details.set_text(
            f"{self.format_memory(disk_used)} ({self.disk_percent:.1f}%) of {self.format_memory(disk_total)}"
        )
        self.disk_indicator.queue_draw()
    
    def start_refresh_timer(self):
        """Start the auto-refresh timer."""
        # Only start if auto refresh is enabled
        if not self.settings.get("auto_refresh", True):
            return
        interval = self.settings.get("refresh_interval")
        self.refresh_timeout_id = GLib.timeout_add(interval, self.on_refresh_timeout)
    
    def on_refresh_timeout(self):
        """Handle refresh timer."""
        self.refresh_processes()
        self.update_system_stats()
        return True  # Continue timer
    
    def on_search_changed(self, entry):
        """Handle search text change."""
        self.refresh_processes()
    
    def on_search_activate(self, entry):
        """Handle Enter key in search - select all visible (filtered) processes."""
        search_text = entry.get_text().strip()
        if not search_text:
            return
        
        # Select all currently visible processes (they are already filtered by search)
        selection = self.tree_view.get_selection()
        for i in range(len(self.list_store)):
            selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        # Clear search and close search bar
        entry.set_text("")
        self.search_bar.set_search_mode(False)
        
        # Focus back to tree view
        self.tree_view.grab_focus()
    
    def select_first_item(self):
        """Select the first item in the process list."""
        if len(self.list_store) > 0 and not self.selected_pids:
            selection = self.tree_view.get_selection()
            selection.select_path(Gtk.TreePath.new_first())
        return False  # Don't repeat
    
    def on_tree_view_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press in tree view - intercept Space before TreeView handles it."""
        has_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        has_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        
        # Handle Space - toggle Play/Pause auto refresh
        if keyval == Gdk.KEY_space and not has_ctrl and not has_alt and not has_shift:
            self.auto_refresh_button.set_active(not self.auto_refresh_button.get_active())
            return True  # Event handled, don't let TreeView process it
        
        return False  # Let TreeView handle other keys
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press for global shortcuts and search."""
        # Check modifier keys
        has_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        has_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        
        # Handle Escape key to close search bar
        if keyval == Gdk.KEY_Escape:
            if self.search_bar.get_search_mode():
                self.search_entry.set_text("")
                self.search_bar.set_search_mode(False)
                self.tree_view.grab_focus()
                return True  # Event handled
            return False
        
        # Handle Backspace - open search and clear search term
        if keyval == Gdk.KEY_BackSpace and not has_ctrl and not has_alt:
            self.search_bar.set_search_mode(True)
            self.search_entry.set_text("")
            self.search_entry.grab_focus()
            return True  # Event handled
        
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
    
    def terminate_selected_processes(self):
        """Terminate selected processes using SIGTERM."""
        if not self.selected_pids:
            return
        
        processes = []
        for pid, info in self.selected_pids.items():
            processes.append({'pid': pid, 'name': info.get('name', 'Unknown')})
        
        if self.settings.get("confirm_kill"):
            self.show_termination_dialog(processes)
        else:
            # Send SIGTERM to all selected processes
            for pid in list(self.selected_pids.keys()):
                try:
                    self.process_manager.kill_process(pid, signal.SIGTERM)
                    if pid in self.selected_pids:
                        del self.selected_pids[pid]
                except Exception as e:
                    self.show_error(f"Failed to terminate process {pid}: {e}")
            GLib.timeout_add(500, self.refresh_processes)
    
    def force_kill_selected_processes(self):
        """Force kill selected processes using SIGKILL."""
        if not self.selected_pids:
            return
        
        # Send SIGKILL to all selected processes (no confirmation for force kill)
        for pid in list(self.selected_pids.keys()):
            try:
                self.process_manager.kill_process(pid, signal.SIGKILL)
                if pid in self.selected_pids:
                    del self.selected_pids[pid]
            except Exception as e:
                self.show_error(f"Failed to kill process {pid}: {e}")
        
        GLib.timeout_add(500, self.refresh_processes)
    
    def on_kill_process(self, button):
        """Kill selected process(es)."""
        selection = self.tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return
        
        processes = []
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, 6)
            name = model.get_value(iter, 0)
            processes.append({'pid': pid, 'name': name})
        
        if self.settings.get("confirm_kill"):
            self.show_termination_dialog(processes)
        else:
            self.kill_processes_direct([p['pid'] for p in processes])
    
    def show_termination_dialog(self, processes):
        """Show termination dialog with status tracking."""
        dialog = TerminationDialog(self, self.process_manager, processes)
        dialog.present()
    
    def kill_processes_direct(self, pids):
        """Kill the specified processes directly without dialog."""
        for pid in pids:
            try:
                self.process_manager.kill_process(pid)
                # Remove from persistent selection
                if pid in self.selected_pids:
                    del self.selected_pids[pid]
            except Exception as e:
                self.show_error(f"Failed to kill process {pid}: {e}")
        
        # Refresh after killing
        GLib.timeout_add(500, self.refresh_processes)
    
    def show_error(self, message):
        """Show error toast."""
        toast = Adw.Toast(title=message, timeout=3)
        # Need toast overlay - simplified for now
        print(f"Error: {message}")
    
    def on_right_click(self, gesture, n_press, x, y):
        """Handle right-click context menu."""
        # Get clicked row
        path_info = self.tree_view.get_path_at_pos(int(x), int(y))
        if path_info:
            path, column, cell_x, cell_y = path_info
            selection = self.tree_view.get_selection()
            
            if not selection.path_is_selected(path):
                selection.unselect_all()
                selection.select_path(path)
            
            # Show context menu
            self.show_context_menu(x, y)
    
    def show_context_menu(self, x, y):
        """Show the process context menu."""
        # Create a simple popover menu
        popover = Gtk.PopoverMenu()
        popover.set_parent(self.tree_view)
        
        # Create menu model
        menu = Gio.Menu()
        
        # End Process action
        end_action = Gio.SimpleAction.new("context-kill", None)
        end_action.connect("activate", lambda a, p: self.on_kill_process(None))
        self.add_action(end_action)
        menu.append("End Process", "win.context-kill")
        
        popover.set_menu_model(menu)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()
    
    def on_close_request(self, window):
        """Handle window close."""
        # Stop refresh timer
        if self.refresh_timeout_id:
            GLib.source_remove(self.refresh_timeout_id)
        
        # Save window size
        width = self.get_width()
        height = self.get_height()
        self.settings.set("window_width", width)
        self.settings.set("window_height", height)
        
        return False  # Allow close

