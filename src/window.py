# SPDX-License-Identifier: GPL-3.0-or-later
# Main window

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import os
import signal
from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk
from .process_manager import ProcessManager
from .stats import SystemStats, GPUStats, PortStats, IOStats
from .process_history import ProcessHistory
from .dialogs import (
    ProcessDetailsDialog,
    ReniceDialog,
    ExportDialog,
    ShortcutsWindow,
    TerminationDialog,
)
from .tabs import GPUTabMixin, PortsTabMixin
from .ui import StatsBarMixin, SelectionPanelMixin, BookmarksPanelMixin, HighUsagePanelMixin
from .handlers import KeyboardHandlerMixin, ContextMenuMixin, ProcessActionsMixin
from .utils import parse_size_str, format_bytes, format_rate


# NOTE: All dialog classes have been moved to src/dialogs/ package
# NOTE: GPU and Ports tab methods are provided by mixins from src/tabs/ package
# NOTE: UI panels are provided by mixins from src/ui/ package
# NOTE: Handlers are provided by mixins from src/handlers/ package


class ProcessManagerWindow(
    GPUTabMixin, 
    PortsTabMixin, 
    StatsBarMixin,
    SelectionPanelMixin,
    BookmarksPanelMixin,
    HighUsagePanelMixin,
    KeyboardHandlerMixin,
    ContextMenuMixin,
    ProcessActionsMixin,
    Adw.ApplicationWindow
):
    """Main application window."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        app = self.get_application()
        self.settings = app.settings
        self.process_manager = ProcessManager()
        self.system_stats = SystemStats()
        self.gpu_stats = GPUStats()
        self.port_stats = PortStats()
        self.io_stats = IOStats()
        
        # Initialize process history if enabled
        history_enabled = self.settings.get("history_enabled", True)
        max_history_days = self.settings.get("history_max_days", 7)
        if history_enabled:
            self.process_history = ProcessHistory(max_history_days=max_history_days)
        else:
            self.process_history = None
        
        # Current active tab
        self.current_tab = 'processes'  # 'processes', 'gpu', or 'ports'
        
        # Persistent selection tracking
        # Key: PID, Value: dict with process info (name, user, etc.)
        self.selected_pids = {}
        self._updating_selection = False  # Flag to prevent recursive selection updates
        
        # Ports tab: unique port keys for precise selection tracking
        # Format: "pid:protocol:local_port"
        self.selected_port_keys = set()
        
        # Cache for previous process stats (for change detection)
        # Key: PID, Value: dict with cpu, memory values
        self._prev_process_stats = {}
        
        # Track processes that have ever used GPU (for GPU tab filtering)
        # Set of PIDs that have used GPU at least once
        self._gpu_used_pids = set()
        
        # Window setup
        self.set_title("Process Manager")
        # Restore window size from settings
        width = self.settings.get("window_width", 900)
        height = self.settings.get("window_height", 600)
        self.set_default_size(width, height)
        
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
        # Toast overlay for error messages
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)
        
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
        
        # Tree view toggle button
        self.tree_view_button = Gtk.ToggleButton()
        tree_view_mode = self.settings.get("tree_view_mode", False)
        self.tree_view_button.set_active(tree_view_mode)
        # Use a fallback icon if view-list-tree-symbolic doesn't exist
        self.tree_view_button.set_icon_name("view-list-symbolic")
        self.tree_view_button.set_tooltip_text("Tree View" if not tree_view_mode else "List View")
        self.tree_view_button.connect("toggled", self.on_tree_view_toggled)
        header.pack_start(self.tree_view_button)
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self.create_menu())
        header.pack_end(menu_button)
        
        main_box.append(header)
        
        # Search bar (hidden by default, shown when typing)
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activate)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_search_mode(False)  # Hidden by default
        
        search_box.append(self.search_bar)
        
        main_box.append(search_box)
        
        # Key controller for typing to trigger search and tab switching
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        # Create ViewStack for tabs
        self.view_stack = Adw.ViewStack()
        
        # Processes tab
        processes_page = self.create_processes_tab()
        self.view_stack.add_titled(processes_page, "processes", "Processes")
        
        # GPU tab
        gpu_page = self.create_gpu_tab()
        self.view_stack.add_titled(gpu_page, "gpu", "GPU")
        
        # Ports tab
        ports_page = self.create_ports_tab()
        self.view_stack.add_titled(ports_page, "ports", "Ports")
        
        # Set initial visible tab
        self.view_stack.set_visible_child_name("processes")
        
        # ViewSwitcher for tab navigation
        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(self.view_stack)
        view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(view_switcher)
        
        # Connect to view stack changes
        self.view_stack.connect("notify::visible-child", self.on_tab_changed)
        
        # Set initial button state for default tab (processes)
        # Button should be visible for processes tab with tree view mode
        tree_view_mode = self.settings.get("tree_view_mode", False)
        self.tree_view_button.set_active(tree_view_mode)
        self.tree_view_button.set_icon_name("view-list-symbolic")
        self.tree_view_button.set_tooltip_text("Tree View" if not tree_view_mode else "List View")
        self.tree_view_button.set_visible(True)
        
        main_box.append(self.view_stack)
        
        # System stats bar (shared between tabs)
        self.stats_bar = self.create_stats_bar()
        main_box.append(self.stats_bar)
    
    def create_menu(self):
        """Create the application menu."""
        menu = Gio.Menu()
        
        # File submenu
        file_menu = Gio.Menu()
        file_menu.append("Export...", "win.export")
        menu.append_submenu("File", file_menu)
        
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append("About Process Manager", "app.about")
        menu.append("Quit", "app.quit")
        
        # Add window actions
        export_action = Gio.SimpleAction.new("export", None)
        export_action.connect("activate", lambda a, p: self.on_export())
        self.add_action(export_action)
        
        return menu
    
    def create_processes_tab(self):
        """Create the processes tab content."""
        tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Bookmarks panel (above selection panel)
        self.bookmarks_panel = self.create_bookmarks_panel()
        tab_box.append(self.bookmarks_panel)
        
        # Selection panel (above process list)
        self.selection_panel = self.create_selection_panel()
        tab_box.append(self.selection_panel)
        
        # Process list
        self.process_scrolled = Gtk.ScrolledWindow()
        self.process_scrolled.set_vexpand(True)
        self.process_scrolled.set_hexpand(True)
        self.process_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.process_view = self.create_process_view()
        self.process_scrolled.set_child(self.process_view)
        tab_box.append(self.process_scrolled)
        
        # High usage processes panel (above stats bar)
        self.high_usage_panel = self.create_high_usage_panel()
        tab_box.append(self.high_usage_panel)
        
        return tab_box
    
    def on_tab_changed(self, stack, param):
        """Handle tab change."""
        visible_child = stack.get_visible_child_name()
        if visible_child == "gpu":
            self.current_tab = 'gpu'
            # Hide tree view button on GPU tab
            self.tree_view_button.set_visible(False)
            # Start GPU background monitoring
            self.gpu_stats.start_background_updates(self._on_gpu_data_updated)
            self.refresh_gpu_processes()
            self.update_system_stats()  # Update stats to show GPU section
        elif visible_child == "ports":
            self.current_tab = 'ports'
            # Show button with "Group Processes" label for Ports tab
            self.tree_view_button.set_visible(True)
            group_processes_mode = self.settings.get("group_processes_mode", False)
            self.tree_view_button.set_active(group_processes_mode)
            self.tree_view_button.set_icon_name("view-list-symbolic")
            self.tree_view_button.set_tooltip_text("Group Processes" if not group_processes_mode else "Ungroup Processes")
            # Stop GPU background monitoring when not on GPU tab
            self.gpu_stats.stop_background_updates()
            # Refresh ports
            self.refresh_ports()
            self.update_system_stats()  # Update stats to hide GPU section
            # Update selection panel visibility
            self.update_selection_panel()
        else:
            self.current_tab = 'processes'
            # Show tree view button with normal label for Processes tab
            self.tree_view_button.set_visible(True)
            tree_view_mode = self.settings.get("tree_view_mode", False)
            self.tree_view_button.set_active(tree_view_mode)
            self.tree_view_button.set_icon_name("view-list-symbolic")
            self.tree_view_button.set_tooltip_text("Tree View" if not tree_view_mode else "List View")
            # Stop GPU background monitoring when not on GPU tab
            self.gpu_stats.stop_background_updates()
            # Refresh regular processes
            self.refresh_processes()
            self.update_system_stats()  # Update stats to hide GPU section
    
    
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
            # Start the timer (will stop existing timer if any)
            self.start_refresh_timer()
        else:
            button.set_icon_name("media-playback-start-symbolic")
            button.set_tooltip_text("Start Auto Refresh")
            # Stop the timer
            if self.refresh_timeout_id:
                GLib.source_remove(self.refresh_timeout_id)
                self.refresh_timeout_id = None
    
    def on_tree_view_toggled(self, button):
        """Handle tree view toggle button."""
        if self.current_tab == 'ports':
            # For Ports tab, handle group processes mode
            group_processes_mode = button.get_active()
            self.settings.set("group_processes_mode", group_processes_mode)
            
            # Update tooltip
            if group_processes_mode:
                button.set_tooltip_text("Ungroup Processes")
            else:
                button.set_tooltip_text("Group Processes")
            
            # Refresh ports to apply grouping
            self.refresh_ports()
        else:
            # For Processes tab, handle tree view mode
            tree_view_mode = button.get_active()
            # Save the toggle state
            self.settings.set("tree_view_mode", tree_view_mode)
            
            # Update tooltip
            if tree_view_mode:
                button.set_tooltip_text("List View")
            else:
                button.set_tooltip_text("Tree View")
            
            # Refresh to rebuild view
            self.refresh_processes()
    
    # Map column names to column IDs for sort persistence
    COLUMN_NAME_TO_ID = {
        "name": 0,
        "cpu": 1,
        "memory": 2,
        "started": 3,
        "user": 4,
        "nice": 5,
        "pid": 6,
        "io_read": 7,
        "io_write": 8,
    }
    COLUMN_ID_TO_NAME = {v: k for k, v in COLUMN_NAME_TO_ID.items()}
    
    def create_process_view(self):
        """Create the process list view."""
        # Check if tree view mode is enabled
        tree_view_mode = self.settings.get("tree_view_mode", False)
        
        if tree_view_mode:
            # Create tree store for tree view
            # Columns: name, cpu, memory, started, user, nice, pid, io_read, io_write
            self.tree_store = Gtk.TreeStore(str, str, str, str, str, str, int, str, str)
            self.list_store = self.tree_store  # Use tree_store as list_store for compatibility
        else:
            # Create list store: name, cpu, memory, started, user, nice, pid, io_read, io_write
            self.list_store = Gtk.ListStore(str, str, str, str, str, str, int, str, str)
        
        # Create tree view
        tree_view = Gtk.TreeView(model=self.list_store)
        tree_view.set_headers_clickable(True)
        tree_view.set_enable_search(False)
        tree_view.set_search_column(-1)  # Disable search completely
        tree_view.set_show_expanders(tree_view_mode)
        if tree_view_mode:
            tree_view.set_level_indentation(20)
        
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
            ("Read/s", 7, 80),
            ("Write/s", 8, 80),
        ]
        
        for i, (title, col_id, width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if col_id == 0:  # Process name - ellipsize
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            if col_id in (7, 8):  # Right-align I/O columns
                renderer.set_property("xalign", 1.0)
            
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_resizable(True)
            column.set_min_width(60)
            column.set_fixed_width(width)
            column.set_sort_column_id(col_id)
            column.set_clickable(True)
            
            tree_view.append_column(column)
        
        # Custom sorting for numeric columns
        self._attach_sort_functions(self.list_store)
        
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
    
    def _attach_sort_functions(self, store):
        """Attach custom sort functions to a store.
        
        Args:
            store: Gtk.ListStore or Gtk.TreeStore to attach sort functions to.
        """
        store.set_sort_func(1, self.sort_percent, None)     # CPU
        store.set_sort_func(2, self.sort_memory, None)      # Memory
        store.set_sort_func(3, self.sort_started, None)     # Started
        store.set_sort_func(5, self.sort_nice, None)        # Nice
        store.set_sort_func(6, self.sort_pid, None)         # PID
        store.set_sort_func(7, self.sort_io_rate, 7)        # Read/s
        store.set_sort_func(8, self.sort_io_rate, 8)        # Write/s
    
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
        val1 = parse_size_str(model.get_value(iter1, 2))
        val2 = parse_size_str(model.get_value(iter2, 2))
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
    
    def sort_io_rate(self, model, iter1, iter2, col_id):
        """Sort by I/O rate value (columns 7 or 8).
        
        Parses values like "1.5 MiB", "256 KiB", "0 B" to bytes for comparison.
        """
        val1 = parse_size_str(model.get_value(iter1, col_id))
        val2 = parse_size_str(model.get_value(iter2, col_id))
        # Reversed for descending on first click (highest I/O first)
        return (val2 > val1) - (val2 < val1)
    
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
    
    def _get_current_tree_view_info(self):
        """Get current tab's tree view, list store, and PID column index."""
        if self.current_tab == 'gpu':
            return self.gpu_tree_view, self.gpu_list_store, 3
        elif self.current_tab == 'ports':
            return self.ports_tree_view, self.ports_list_store, 1
        else:
            return self.tree_view, self.list_store, 6
    
    def _refresh_current_tab(self):
        """Refresh the current tab's process list."""
        if self.current_tab == 'gpu':
            self.refresh_gpu_processes()
        elif self.current_tab == 'ports':
            self.refresh_ports()
        else:
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
    
    # Override toggle_bookmark from BookmarksPanelMixin to add toast notification
    def toggle_bookmark(self, pid):
        """Toggle bookmark status for a process."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        if pid in bookmarked_pids:
            bookmarked_pids.remove(pid)
            toast = Adw.Toast(title="Process unbookmarked", timeout=2)
        else:
            bookmarked_pids.append(pid)
            toast = Adw.Toast(title="Process bookmarked", timeout=2)
        self.settings.set("bookmarked_pids", bookmarked_pids)
        self.toast_overlay.add_toast(toast)
        self.update_bookmarks_panel()
    
    def on_selection_changed(self, selection):
        """Handle selection changes for processes tab - sync with persistent selected_pids."""
        self._handle_selection_changed(selection, self.list_store, pid_column=6, user_column=4)
    
    def _handle_selection_changed(self, selection, list_store, pid_column, user_column):
        """Common handler for selection changes in both tabs."""
        if self._updating_selection:
            return
        
        model, paths = selection.get_selected_rows()
        
        # Build set of currently selected PIDs
        newly_selected = set()
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, pid_column)
            newly_selected.add(pid)
            
            # Add to persistent selection if not already there
            if pid not in self.selected_pids:
                name = model.get_value(iter, 0)
                user = model.get_value(iter, user_column) if user_column else 'N/A'
                cpu_str = model.get_value(iter, 1)
                mem_str = model.get_value(iter, 2)
                self.selected_pids[pid] = {
                    'name': name,
                    'user': user,
                    'cpu_str': cpu_str,
                    'mem_str': mem_str,
                }
            else:
                # Update CPU/memory info
                self.selected_pids[pid]['cpu_str'] = model.get_value(iter, 1)
                self.selected_pids[pid]['mem_str'] = model.get_value(iter, 2)
        
        # Remove PIDs that were deselected (only if they were in list_store)
        pids_in_store = set()
        for row in list_store:
            pids_in_store.add(row[pid_column])
        
        for pid in list(self.selected_pids.keys()):
            if pid in pids_in_store and pid not in newly_selected:
                del self.selected_pids[pid]
        
        # Update the selection panel
        self.update_selection_panel()
    
    def _build_process_tree(self, processes):
        """Build a tree structure from processes based on parent-child relationships.
        
        Returns:
            Dict mapping PID to dict with 'proc' (process data) and 'children' (list of child PIDs)
        """
        tree = {}
        pid_set = set()
        
        # First pass: create entries for all processes
        for proc in processes:
            pid = proc['pid']
            pid_set.add(pid)
            tree[pid] = {'proc': proc, 'children': []}
        
        # Second pass: build parent-child relationships
        roots = []
        for proc in processes:
            pid = proc['pid']
            ppid = proc.get('ppid', 0)
            
            if ppid in tree:
                tree[ppid]['children'].append(pid)
            else:
                roots.append(pid)
        
        return tree, roots
    
    def _populate_tree_store(self, tree_store, parent_iter, tree_data, io_stats_map=None):
        """Populate tree store with process tree data.
        
        Args:
            tree_store: The Gtk.TreeStore to populate.
            parent_iter: Parent iterator or None for root level.
            tree_data: Tree data from _build_process_tree.
            io_stats_map: Optional dict mapping PID to I/O stats.
        """
        tree, roots = tree_data
        for pid in roots:
            self._add_tree_node(tree_store, parent_iter, tree, pid, io_stats_map)
    
    def _add_tree_node(self, tree_store, parent_iter, tree, pid, io_stats_map=None):
        """Add a tree node and its children recursively.
        
        Args:
            tree_store: The Gtk.TreeStore to add to.
            parent_iter: Parent iterator or None.
            tree: The tree structure dict.
            pid: Process ID to add.
            io_stats_map: Optional dict mapping PID to I/O stats.
        """
        if pid not in tree:
            return
        
        node = tree[pid]
        proc = node['proc']
        
        # Get I/O stats
        io_read = "0 B"
        io_write = "0 B"
        if io_stats_map and pid in io_stats_map:
            io_read = self.format_rate(io_stats_map[pid].get('read_bytes_per_sec', 0))
            io_write = self.format_rate(io_stats_map[pid].get('write_bytes_per_sec', 0))
        
        row_data = [
            proc['name'],
            f"{proc['cpu']:.1f}%",
            self.format_memory(proc['memory']),
            proc.get('started', ''),
            proc.get('user', ''),
            str(proc.get('nice', 0)),
            pid,
            io_read,
            io_write,
        ]
        
        iter = tree_store.append(parent_iter, row_data)
        
        # Recursively add children
        for child_pid in sorted(node['children']):
            self._add_tree_node(tree_store, iter, tree, child_pid, io_stats_map)
    
    def _restore_tree_selection(self, tree_store, parent_iter, selection):
        """Restore selection in tree view by PID."""
        iter = tree_store.iter_children(parent_iter)
        while iter:
            pid = tree_store.get_value(iter, 6)
            if pid in self.selected_pids:
                path = tree_store.get_path(iter)
                selection.select_path(path)
            # Recurse into children
            self._restore_tree_selection(tree_store, iter, selection)
            iter = tree_store.iter_next(iter)
    
    def _recreate_tree_view(self):
        """Recreate the process view with tree store for tree view mode."""
        self.tree_store = Gtk.TreeStore(str, str, str, str, str, str, int, str, str)
        self.list_store = self.tree_store
        self._attach_sort_functions(self.list_store)
        self.tree_view.set_model(self.list_store)
        self.tree_view.set_show_expanders(True)
        self.tree_view.set_level_indentation(20)
        
        # Restore sort
        saved_column = self.settings.get("sort_column")
        saved_descending = self.settings.get("sort_descending")
        sort_col_id = self.COLUMN_NAME_TO_ID.get(saved_column, 1)
        sort_order = Gtk.SortType.DESCENDING if saved_descending else Gtk.SortType.ASCENDING
        self.list_store.set_sort_column_id(sort_col_id, sort_order)
        self.list_store.connect("sort-column-changed", self.on_sort_column_changed)
    
    def _recreate_list_view(self):
        """Recreate the process view with list store for flat view mode."""
        self.list_store = Gtk.ListStore(str, str, str, str, str, str, int, str, str)
        self._attach_sort_functions(self.list_store)
        self.tree_view.set_model(self.list_store)
        self.tree_view.set_show_expanders(False)
        
        # Restore sort
        saved_column = self.settings.get("sort_column")
        saved_descending = self.settings.get("sort_descending")
        sort_col_id = self.COLUMN_NAME_TO_ID.get(saved_column, 1)
        sort_order = Gtk.SortType.DESCENDING if saved_descending else Gtk.SortType.ASCENDING
        self.list_store.set_sort_column_id(sort_col_id, sort_order)
        self.list_store.connect("sort-column-changed", self.on_sort_column_changed)
    
    def refresh_processes(self):
        """Refresh the process list."""
        # Only refresh if we're on the processes tab
        if self.current_tab != 'processes':
            return
        
        show_all = self.all_user_button.get_active()
        my_processes = not show_all
        show_kernel_threads = self.settings.get("show_kernel_threads", False)
        
        # Get processes
        processes = self.process_manager.get_processes(
            show_all=show_all,
            my_processes=my_processes,
            active_only=False,
            show_kernel_threads=show_kernel_threads
        )
        
        # Get all processes for cleaning up selection
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
        if pids_to_remove:
            # Show notification for removed processes
            removed_names = [self.selected_pids[pid].get('name', f'PID {pid}') for pid in pids_to_remove]
            if len(removed_names) == 1:
                message = f"Process '{removed_names[0]}' has exited"
            else:
                message = f"{len(removed_names)} selected processes have exited"
            toast = Adw.Toast(title=message, timeout=3)
            self.toast_overlay.add_toast(toast)
            
            for pid in pids_to_remove:
                del self.selected_pids[pid]
        
        # Update cpu/memory info for selected processes
        for pid in self.selected_pids:
            if pid in all_process_map:
                proc = all_process_map[pid]
                self.selected_pids[pid]['cpu_str'] = f"{proc['cpu']:.1f}%"
                self.selected_pids[pid]['mem_str'] = self.format_memory(proc['memory'])
        
        # Get search text
        search_text = self.search_entry.get_text().lower()
        
        def matches_search(proc):
            """Check if process matches search text."""
            if not search_text:
                return True
            return search_text in proc['name'].lower() or search_text in str(proc['pid'])
        
        # Filter by search
        filtered_processes = [p for p in processes if matches_search(p)]
        
        # When searching, hide already selected items from results
        if search_text:
            filtered_processes = [p for p in filtered_processes if p['pid'] not in self.selected_pids]
        else:
            # When not searching, add selected processes that are not in filtered list
            filtered_pids = {p['pid'] for p in filtered_processes}
            for pid in self.selected_pids:
                if pid not in filtered_pids and pid in all_pids:
                    filtered_processes.append(all_process_map[pid])
        
        # Get I/O stats for all processes in filtered list
        all_pids_list = [p['pid'] for p in filtered_processes]
        io_stats_map = self.io_stats.get_all_processes_io(all_pids_list)
        
        # Check if we need tree or list view
        tree_view_mode = self.settings.get("tree_view_mode", False)
        
        # Recreate store if mode changed
        current_is_tree = isinstance(self.list_store, Gtk.TreeStore)
        if tree_view_mode and not current_is_tree:
            self._recreate_tree_view()
        elif not tree_view_mode and current_is_tree:
            self._recreate_list_view()
        
        # Save scroll position as ratio before updating
        vadj = self.process_scrolled.get_vadjustment()
        scroll_value = vadj.get_value()
        old_upper = vadj.get_upper()
        old_page_size = vadj.get_page_size()
        # Calculate scroll ratio (0.0 = top, 1.0 = bottom)
        old_max_scroll = old_upper - old_page_size
        scroll_ratio = scroll_value / old_max_scroll if old_max_scroll > 0 else 0.0
        
        # Double buffering: Create new model, populate it, then swap
        # This prevents scroll-to-top flash caused by clear()
        self._updating_selection = True
        
        if tree_view_mode:
            new_store = Gtk.TreeStore(str, str, str, str, str, str, int, str, str)
            # Build tree and populate new store
            tree_data = self._build_process_tree(filtered_processes)
            self._populate_tree_store(new_store, None, tree_data, io_stats_map)
        else:
            new_store = Gtk.ListStore(str, str, str, str, str, str, int, str, str)
            # Populate new store
            for proc in filtered_processes:
                pid = proc['pid']
                io_read = "0 B"
                io_write = "0 B"
                if pid in io_stats_map:
                    io_read = self.format_rate(io_stats_map[pid].get('read_bytes_per_sec', 0))
                    io_write = self.format_rate(io_stats_map[pid].get('write_bytes_per_sec', 0))
                
                new_store.append([
                    proc['name'],
                    f"{proc['cpu']:.1f}%",
                    self.format_memory(proc['memory']),
                    proc.get('started', ''),
                    proc.get('user', ''),
                    str(proc.get('nice', 0)),
                    pid,
                    io_read,
                    io_write,
                ])
        
        # Attach sort functions to new store
        self._attach_sort_functions(new_store)
        
        # Restore sort column from old store
        sort_col_id, sort_order = self.list_store.get_sort_column_id()
        if sort_col_id is not None and sort_col_id >= 0:
            new_store.set_sort_column_id(sort_col_id, sort_order)
        
        # Connect sort change handler
        new_store.connect("sort-column-changed", self.on_sort_column_changed)
        
        # Set up one-shot handler to restore scroll immediately when adjustment changes
        def restore_scroll_on_change(adj):
            new_upper = adj.get_upper()
            new_page_size = adj.get_page_size()
            new_max_scroll = new_upper - new_page_size
            if new_max_scroll > 0:
                new_scroll_value = scroll_ratio * new_max_scroll
                adj.set_value(new_scroll_value)
            adj.disconnect_by_func(restore_scroll_on_change)
        
        vadj.connect("changed", restore_scroll_on_change)
        
        # Atomic swap: Set new model to tree view
        self.list_store = new_store
        self.tree_view.set_model(self.list_store)
        
        # Restore selection
        selection = self.tree_view.get_selection()
        if self.selected_pids:
            if tree_view_mode:
                self._restore_tree_selection(self.list_store, None, selection)
            else:
                for i, row in enumerate(self.list_store):
                    if row[6] in self.selected_pids:
                        selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        self._updating_selection = False
        
        # Update panels
        self.update_selection_panel()
        self.update_bookmarks_panel()
        self.update_high_usage_panel(processes)
        
        # Record to history
        if self.process_history:
            self.process_history.update_processes(processes)
    
    def format_memory(self, bytes_val):
        """Format memory in human-readable format."""
        return format_bytes(bytes_val)
    
    def format_rate(self, bytes_per_sec):
        """Format I/O rate in human-readable format."""
        return format_rate(bytes_per_sec)
    
    def format_bytes(self, bytes_val):
        """Format bytes in human-readable format."""
        return format_bytes(bytes_val)
    
    def start_refresh_timer(self):
        """Start the auto-refresh timer."""
        # Stop any existing timer first to avoid duplicates
        if self.refresh_timeout_id:
            GLib.source_remove(self.refresh_timeout_id)
            self.refresh_timeout_id = None
        
        # Check button state (source of truth) or settings as fallback
        auto_refresh = self.auto_refresh_button.get_active() if hasattr(self, 'auto_refresh_button') else self.settings.get("auto_refresh", True)
        if not auto_refresh:
            return
        
        interval = self.settings.get("refresh_interval")
        self.refresh_timeout_id = GLib.timeout_add(interval, self.on_refresh_timeout)
    
    def on_refresh_timeout(self):
        """Handle refresh timer."""
        if self.current_tab == 'gpu':
            self.refresh_gpu_processes()
            self.update_system_stats()  # Also updates GPU stats
        elif self.current_tab == 'ports':
            self.refresh_ports()
            self.update_system_stats()
        else:
            self.refresh_processes()
            self.update_system_stats()
        return True  # Continue timer
    
    def select_first_item(self):
        """Select the first item in the process list."""
        if len(self.list_store) > 0 and not self.selected_pids:
            selection = self.tree_view.get_selection()
            selection.select_path(Gtk.TreePath.new_first())
        return False  # Don't repeat
    
    def on_close_request(self, window):
        """Handle window close."""
        # Stop refresh timer
        if self.refresh_timeout_id:
            GLib.source_remove(self.refresh_timeout_id)
        
        # Stop GPU background updates
        self.gpu_stats.stop_background_updates()
        
        # Save window size
        width = self.get_width()
        height = self.get_height()
        self.settings.set("window_width", width)
        self.settings.set("window_height", height)
        
        # Save process history
        if self.process_history:
            self.process_history.save_history()
        
        return False  # Allow close
    
    def show_selected_process_details(self):
        """Show process details dialog for the selected process."""
        tree_view, list_store, pid_col = self._get_current_tree_view_info()
        selection = tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        
        # Only show details for single selection
        if len(paths) != 1:
            return
        
        path = paths[0]
        iter = model.get_iter(path)
        pid = model.get_value(iter, pid_col)
        name = model.get_value(iter, 0)
        cpu_str = model.get_value(iter, 1)
        mem_str = model.get_value(iter, 2)
        
        # Build process info dict with additional details from all_processes
        process_info = {
            'name': name,
            'cpu_str': cpu_str,
            'mem_str': mem_str,
        }
        
        # Get additional info from cached selected_pids or fetch fresh data
        if pid in self.selected_pids:
            process_info['user'] = self.selected_pids[pid].get('user', 'N/A')
        
        # Get more details from the process list
        all_processes = self.process_manager.get_processes(
            show_all=True,
            my_processes=False,
            active_only=False,
            show_kernel_threads=True
        )
        
        for proc in all_processes:
            if proc['pid'] == pid:
                process_info['user'] = proc.get('user', 'N/A')
                process_info['nice'] = proc.get('nice', 'N/A')
                process_info['started'] = proc.get('started', 'N/A')
                process_info['state'] = proc.get('state', 'N/A')
                break
        
        # Show the details dialog
        dialog = ProcessDetailsDialog(self, self.process_manager, pid, process_info)
        dialog.present()
    
    def on_change_priority(self, button):
        """Change priority (renice) for selected process(es)."""
        tree_view, _, pid_col = self._get_current_tree_view_info()
        selection = tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return
        
        processes = []
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, pid_col)
            name = model.get_value(iter, 0)
            # Get current nice value
            nice_str = model.get_value(iter, 5)  # Nice column
            try:
                nice = int(nice_str)
            except (ValueError, TypeError):
                nice = 0
            processes.append({'pid': pid, 'name': name, 'nice': nice})
        
        dialog = ReniceDialog(self, self.process_manager, processes)
        dialog.present()
    
    def on_export(self):
        """Export process list to file."""
        dialog = ExportDialog(self, self.process_manager, self.tree_view, self.list_store, self.selected_pids)
        dialog.present()
