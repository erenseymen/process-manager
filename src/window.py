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
from .gpu_stats import GPUStats
from .port_stats import PortStats
from .io_stats import IOStats
from .process_history import ProcessHistory
from .dialogs import (
    ProcessDetailsDialog,
    ReniceDialog,
    ExportDialog,
    ShortcutsWindow,
    TerminationDialog,
)
from .tabs import GPUTabMixin, PortsTabMixin


# NOTE: All dialog classes have been moved to src/dialogs/ package
# NOTE: GPU and Ports tab methods are provided by mixins from src/tabs/ package


class ProcessManagerWindow(GPUTabMixin, PortsTabMixin, Adw.ApplicationWindow):
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
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.process_view = self.create_process_view()
        scrolled.set_child(self.process_view)
        tab_box.append(scrolled)
        
        # High usage processes panel (above stats bar)
        self.high_usage_panel = self.create_high_usage_panel()
        tab_box.append(self.high_usage_panel)
        
        return tab_box
    
    
    
    def create_selection_panel_for_tab(self, tab_name):
        """Create a selection panel for a specific tab (reuses the same selected_pids)."""
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
        title_label = Gtk.Label(label="Selected:")
        title_label.add_css_class("heading")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        header_box.append(title_label)
        
        # End Process button
        end_btn = Gtk.Button()
        end_btn.set_icon_name("process-stop-symbolic")
        end_btn.set_tooltip_text("End Selected Processes")
        end_btn.add_css_class("destructive-action")
        end_btn.connect("clicked", self.on_kill_process)
        header_box.append(end_btn)
        
        # Clear all button
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-all-symbolic")
        clear_btn.set_tooltip_text("Clear Selection")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self.on_clear_selection)
        header_box.append(clear_btn)
        
        panel_box.append(header_box)
        
        # Scrolled window for process comparison list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(200)
        scrolled.set_propagate_natural_height(True)
        
        # ListBox for vertical process comparison
        selection_list = Gtk.ListBox()
        selection_list.set_selection_mode(Gtk.SelectionMode.NONE)
        selection_list.add_css_class("selection-comparison-list")
        selection_list.set_margin_start(12)
        selection_list.set_margin_end(12)
        selection_list.set_margin_bottom(8)
        scrolled.set_child(selection_list)
        panel_box.append(scrolled)
        
        # Bottom separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        panel_box.append(sep)
        
        # Initially hidden
        panel_box.set_visible(False)
        
        # Store references based on tab
        if tab_name == 'gpu':
            self.gpu_selection_title = title_label
            self.gpu_selection_list = selection_list
        elif tab_name == 'ports':
            self.ports_selection_title = title_label
            self.ports_selection_list = selection_list
        
        return panel_box
    
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
    
    def sort_io_rate(self, model, iter1, iter2, col_id):
        """Sort by I/O rate value (columns 7 or 8).
        
        Parses values like "1.5 MiB", "256 KiB", "0 B" to bytes for comparison.
        """
        def parse_rate(s):
            s = s.strip()
            if not s or s == '-':
                return 0
            try:
                if s.endswith('/s'):
                    s = s[:-2].strip()
                if s.endswith('GiB'):
                    return float(s[:-3]) * 1024 * 1024 * 1024
                elif s.endswith('MiB'):
                    return float(s[:-3]) * 1024 * 1024
                elif s.endswith('KiB'):
                    return float(s[:-3]) * 1024
                elif s.endswith('B'):
                    return float(s[:-1])
                return float(s)
            except (ValueError, AttributeError):
                return 0
        
        val1 = parse_rate(model.get_value(iter1, col_id))
        val2 = parse_rate(model.get_value(iter2, col_id))
        # Reversed for descending on first click (highest I/O first)
        return (val2 > val1) - (val2 < val1)
    
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
    
    def create_bookmarks_panel(self):
        """Create the bookmarks panel showing bookmarked processes."""
        # Main container
        panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel_box.add_css_class("bookmarks-panel")
        
        # Header row with title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(8)
        header_box.set_margin_top(6)
        header_box.set_margin_bottom(4)
        
        # Title label
        self.bookmarks_title = Gtk.Label(label="Bookmarks:")
        self.bookmarks_title.add_css_class("heading")
        self.bookmarks_title.set_halign(Gtk.Align.START)
        self.bookmarks_title.set_hexpand(True)
        header_box.append(self.bookmarks_title)
        
        panel_box.append(header_box)
        
        # Scrolled window for bookmarks list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(150)
        scrolled.set_propagate_natural_height(True)
        
        # ListBox for bookmarks
        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.bookmarks_list.add_css_class("bookmarks-list")
        self.bookmarks_list.set_margin_start(12)
        self.bookmarks_list.set_margin_end(12)
        self.bookmarks_list.set_margin_bottom(8)
        self.bookmarks_list.connect("row-activated", self.on_bookmark_activated)
        scrolled.set_child(self.bookmarks_list)
        panel_box.append(scrolled)
        
        # Bottom separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        panel_box.append(sep)
        
        # Initially hidden
        panel_box.set_visible(False)
        
        return panel_box
    
    def update_bookmarks_panel(self):
        """Update the bookmarks panel with current bookmarked processes."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        count = len(bookmarked_pids)
        
        # Show/hide panel based on bookmarks
        self.bookmarks_panel.set_visible(count > 0)
        
        if count == 0:
            return
        
        # Update title
        self.bookmarks_title.set_label(f"Bookmarks ({count}):")
        
        # Clear existing rows
        while True:
            child = self.bookmarks_list.get_row_at_index(0)
            if child is None:
                break
            self.bookmarks_list.remove(child)
        
        # Get all processes to find bookmarked ones
        all_processes = self.process_manager.get_processes(
            show_all=True,
            my_processes=False,
            active_only=False,
            show_kernel_threads=True
        )
        process_map = {p['pid']: p for p in all_processes}
        
        # Add bookmarked processes
        for pid in bookmarked_pids:
            if pid in process_map:
                proc = process_map[pid]
                row = self.create_bookmark_row(proc)
                self.bookmarks_list.append(row)
            else:
                # Process no longer exists, remove from bookmarks
                bookmarked_pids.remove(pid)
                self.settings.set("bookmarked_pids", bookmarked_pids)
    
    def create_bookmark_row(self, proc):
        """Create a row for a bookmarked process."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        
        # Process name
        name_label = Gtk.Label(label=proc.get('name', 'Unknown'))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(name_label)
        
        # CPU and Memory
        cpu_str = f"{proc.get('cpu', 0):.1f}%"
        mem_str = self.format_memory(proc.get('memory', 0))
        info_label = Gtk.Label(label=f"{cpu_str} | {mem_str}")
        info_label.set_halign(Gtk.Align.END)
        info_label.add_css_class("dim-label")
        box.append(info_label)
        
        # Unbookmark button
        unbookmark_btn = Gtk.Button()
        unbookmark_btn.set_icon_name("bookmark-remove-symbolic")
        unbookmark_btn.set_tooltip_text("Unbookmark")
        unbookmark_btn.add_css_class("flat")
        unbookmark_btn.add_css_class("circular")
        unbookmark_btn.connect("clicked", lambda b, p=proc['pid']: self.toggle_bookmark(p))
        box.append(unbookmark_btn)
        
        row.set_child(box)
        return row
    
    def on_bookmark_activated(self, list_box, row):
        """Handle bookmark row activation - select the process in the main list."""
        box = row.get_child()
        # Find the name label to get process name
        for child in box:
            if isinstance(child, Gtk.Label) and child.get_halign() == Gtk.Align.START:
                name = child.get_text()
                # Find and select the process in the main list
                self._select_process_by_name(name)
                break
    
    def _select_process_by_name(self, name):
        """Select a process in the main list by name (selects first match)."""
        for i, row in enumerate(self.list_store):
            if row[0] == name:  # Process name column
                path = Gtk.TreePath.new_from_indices([i])
                selection = self.tree_view.get_selection()
                selection.select_path(path)
                self.tree_view.scroll_to_cell(path, None, False, 0, 0)
                break
    
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
        
        # Get current tab's panel and list components
        if self.current_tab == 'gpu':
            panel = self.gpu_selection_panel
            title_label = self.gpu_selection_title
            selection_list = self.gpu_selection_list
        elif self.current_tab == 'ports':
            panel = self.ports_selection_panel
            title_label = self.ports_selection_title
            selection_list = self.ports_selection_list
        else:
            panel = self.selection_panel
            title_label = self.selection_title
            selection_list = self.selection_list
        
        # Show/hide panel based on selection
        panel.set_visible(count > 0)
        
        # Also update the other tab's panel visibility
        if self.current_tab == 'gpu':
            self.selection_panel.set_visible(False)
            if hasattr(self, 'ports_selection_panel'):
                self.ports_selection_panel.set_visible(False)
        elif self.current_tab == 'ports':
            self.selection_panel.set_visible(False)
            if hasattr(self, 'gpu_selection_panel'):
                self.gpu_selection_panel.set_visible(False)
        else:
            if hasattr(self, 'gpu_selection_panel'):
                self.gpu_selection_panel.set_visible(False)
            if hasattr(self, 'ports_selection_panel'):
                self.ports_selection_panel.set_visible(False)
        
        if count == 0:
            return
        
        # Calculate totals
        total_cpu = sum(self.parse_cpu_str(info.get('cpu_str', '0%')) 
                       for info in self.selected_pids.values())
        total_mem = sum(self.parse_mem_str(info.get('mem_str', '0 B')) 
                       for info in self.selected_pids.values())
        
        # Update title with totals
        title_label.set_label(
            f"Selected ({count}): CPU {total_cpu:.1f}% | Mem {self.format_memory(total_mem)}"
        )
        
        # Clear existing rows
        while True:
            child = selection_list.get_row_at_index(0)
            if child is None:
                break
            selection_list.remove(child)
        
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
            selection_list.append(row)
    
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
        # Update tree view selection for current tab
        self._updating_selection = True
        tree_view, list_store, pid_col = self._get_current_tree_view_info()
        selection = tree_view.get_selection()
        for pid in pids:
            for i, row in enumerate(list_store):
                if row[pid_col] == pid:
                    selection.unselect_path(Gtk.TreePath.new_from_indices([i]))
                    break
        self._updating_selection = False
    
    def on_clear_selection(self, button):
        """Clear all selections."""
        self.selected_pids.clear()
        self.update_selection_panel()
        # Update tree view selection for both tabs
        self._updating_selection = True
        self.tree_view.get_selection().unselect_all()
        if hasattr(self, 'gpu_tree_view'):
            self.gpu_tree_view.get_selection().unselect_all()
        self._updating_selection = False
        self._refresh_current_tab()
    
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
    
    def is_bookmarked(self, pid):
        """Check if a process is bookmarked."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        return pid in bookmarked_pids
    
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
        show_kernel_threads = self.settings.get("show_kernel_threads", False)
        
        # Get User/All filter setting
        show_all = self.all_user_button.get_active() if hasattr(self, 'all_user_button') else True
        my_processes = not show_all
        
        # Get current user UID for filtering
        current_uid = os.getuid()
        
        # Process names to filter out (our own refresh processes)
        filtered_names = {'ps', 'flatpak-spawn'}
        
        # Helper function to check if process should be filtered
        def should_filter_process(proc_name):
            """Check if process should be filtered from high usage panel."""
            return proc_name in filtered_names
        
        # Helper function to check if process is a kernel thread
        def is_kernel_thread(proc):
            """Check if process is a kernel thread (PPID 2 is kthreadd or PID 2)."""
            ppid = proc.get('ppid', 0)
            pid = proc.get('pid', 0)
            return ppid == 2 or pid == 2
        
        # Get total memory for percentage calculation
        stats = self.system_stats.get_memory_info()
        mem_total = stats['mem_total']
        
        # Find processes with significant changes
        changed_cpu = []
        changed_mem = []
        started_processes = []
        ended_processes = []
        
        # Build current stats and detect changes
        current_stats = {}
        current_pids = set()
        for proc in processes:
            # Skip our own refresh processes
            if should_filter_process(proc['name']):
                continue
            
            # Skip kernel threads if not showing them
            if not show_kernel_threads and is_kernel_thread(proc):
                continue
            
            # Respect User/All filter
            if my_processes:
                proc_uid = proc.get('uid', -1)
                if proc_uid != current_uid:
                    continue
            pid = proc['pid']
            current_pids.add(pid)
            cpu_percent = proc['cpu']
            mem_percent = (proc['memory'] / mem_total * 100) if mem_total > 0 else 0
            
            current_stats[pid] = {
                'cpu': cpu_percent,
                'memory': mem_percent,
                'name': proc['name'],
                'ppid': proc.get('ppid', 0),
                'uid': proc.get('uid', -1)
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
            else:
                # New process started
                started_processes.append({
                    'pid': pid,
                    'name': proc['name'],
                    'cpu': cpu_percent,
                    'memory': mem_percent,
                    'type': 'started'
                })
        
        # Detect ended processes (in previous stats but not in current)
        prev_pids = set(self._prev_process_stats.keys())
        ended_pids = prev_pids - current_pids
        for pid in ended_pids:
            prev_info = self._prev_process_stats[pid]
            # Skip our own refresh processes
            if should_filter_process(prev_info['name']):
                continue
            
            # Skip kernel threads if not showing them
            if not show_kernel_threads:
                prev_ppid = prev_info.get('ppid', 0)
                if prev_ppid == 2 or pid == 2:
                    continue
            
            # Respect User/All filter
            if my_processes:
                prev_uid = prev_info.get('uid', -1)
                if prev_uid != current_uid:
                    continue
            
            ended_processes.append({
                'pid': pid,
                'name': prev_info['name'],
                'type': 'ended'
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
        has_changes = (len(changed_cpu) > 0 or len(changed_mem) > 0 or 
                      len(started_processes) > 0 or len(ended_processes) > 0)
        self.high_usage_panel.set_visible(has_changes)
        
        if not has_changes:
            return
        
        # Add started processes (limit to top 5)
        for proc in started_processes[:5]:
            chip = self.create_high_usage_chip(proc, 'started')
            self.high_usage_flow.append(chip)
        
        # Add ended processes (limit to top 5)
        for proc in ended_processes[:5]:
            chip = self.create_high_usage_chip(proc, 'ended')
            self.high_usage_flow.append(chip)
        
        # Add CPU change processes (avoid duplicates with started/ended)
        started_ended_pids = {p['pid'] for p in started_processes[:5]} | {p['pid'] for p in ended_processes[:5]}
        for proc in changed_cpu[:5]:  # Limit to top 5
            if proc['pid'] not in started_ended_pids:
                chip = self.create_high_usage_chip(proc, 'cpu')
                self.high_usage_flow.append(chip)
        
        # Add memory change processes (avoid duplicates)
        changed_cpu_pids = {p['pid'] for p in changed_cpu[:5]}
        for proc in changed_mem[:5]:  # Limit to top 5
            if proc['pid'] not in started_ended_pids and proc['pid'] not in changed_cpu_pids:
                chip = self.create_high_usage_chip(proc, 'mem')
                self.high_usage_flow.append(chip)
    
    def create_high_usage_chip(self, proc, usage_type):
        """Create a chip widget for a process with significant usage change."""
        chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chip_box.add_css_class("high-usage-chip")
        
        change = proc.get('change', 0)
        
        # Add class based on change direction and type
        if usage_type == 'started':
            chip_box.add_css_class("change-up")
            chip_box.add_css_class("process-started")
        elif usage_type == 'ended':
            chip_box.add_css_class("change-down")
            chip_box.add_css_class("process-ended")
        else:
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
        
        # Change indicator with arrow or status text
        if usage_type == 'started':
            value_text = "Started"
            value_label = Gtk.Label(label=value_text)
            value_label.add_css_class("chip-value")
            chip_box.append(value_label)
            # Make clickable to select the process
            gesture = Gtk.GestureClick()
            gesture.connect("pressed", lambda g, n, x, y: self.select_process_by_pid(proc['pid']))
            chip_box.add_controller(gesture)
        elif usage_type == 'ended':
            value_text = "Ended"
            value_label = Gtk.Label(label=value_text)
            value_label.add_css_class("chip-value")
            chip_box.append(value_label)
            # Ended processes can't be selected, so no click handler
        else:
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
        
        # CPU section
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.cpu_indicator = Gtk.DrawingArea()
        self.cpu_indicator.set_size_request(24, 24)
        self.cpu_indicator.set_draw_func(self.draw_cpu_indicator)
        cpu_box.append(self.cpu_indicator)
        
        cpu_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.cpu_title = Gtk.Label(label="CPU")
        self.cpu_title.add_css_class("heading")
        self.cpu_title.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_title)
        
        self.cpu_details = Gtk.Label(label="0%")
        self.cpu_details.add_css_class("dim-label")
        self.cpu_details.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_details)
        
        self.cpu_load = Gtk.Label(label="Load: 0.00")
        self.cpu_load.add_css_class("dim-label")
        self.cpu_load.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_load)
        
        cpu_box.append(cpu_label_box)
        stats_box.append(cpu_box)
        
        # Separator
        sep_cpu = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep_cpu)
        
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
        
        # GPU stats section (shown when on GPU tab)
        gpu_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(gpu_sep)
        
        gpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.gpu_indicator = Gtk.DrawingArea()
        self.gpu_indicator.set_size_request(24, 24)
        self.gpu_indicator.set_draw_func(self.draw_gpu_indicator)
        gpu_box.append(self.gpu_indicator)
        
        gpu_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.gpu_title = Gtk.Label(label="GPU")
        self.gpu_title.add_css_class("heading")
        self.gpu_title.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_title)
        
        self.gpu_details = Gtk.Label(label="0%")
        self.gpu_details.add_css_class("dim-label")
        self.gpu_details.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_details)
        
        self.gpu_enc_dec = Gtk.Label(label="Enc: 0% | Dec: 0%")
        self.gpu_enc_dec.add_css_class("dim-label")
        self.gpu_enc_dec.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_enc_dec)
        
        gpu_box.append(gpu_label_box)
        stats_box.append(gpu_box)
        self.gpu_stats_section = gpu_box
        self.gpu_stats_sep = gpu_sep
        
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
        
        # Initially hide GPU stats
        self.gpu_stats_section.set_visible(False)
        self.gpu_stats_sep.set_visible(False)
        
        return stats_box
    
    def draw_cpu_indicator(self, area, cr, width, height):
        """Draw circular CPU usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.cpu_percent, (0.2, 0.6, 0.8))
    
    def draw_memory_indicator(self, area, cr, width, height):
        """Draw circular memory usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.mem_percent, (0.8, 0.2, 0.2))
    
    def draw_swap_indicator(self, area, cr, width, height):
        """Draw circular swap usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.swap_percent, (0.2, 0.8, 0.2))
    
    def draw_disk_indicator(self, area, cr, width, height):
        """Draw circular disk usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.disk_percent, (0.2, 0.2, 0.8))
    
    def draw_gpu_indicator(self, area, cr, width, height):
        """Draw circular GPU usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.gpu_percent, (0.8, 0.5, 0.2))
    
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
    cpu_percent = 0
    mem_percent = 0
    swap_percent = 0
    disk_percent = 0
    gpu_percent = 0
    gpu_encoding_percent = 0
    gpu_decoding_percent = 0
    
    def on_selection_changed(self, selection):
        """Handle selection changes for processes tab - sync with persistent selected_pids."""
        self._handle_selection_changed(selection, self.list_store, pid_column=6, user_column=4)
    
    
    def _handle_selection_changed(self, selection, list_store, pid_column, user_column):
        """Common handler for selection changes in both tabs."""
        if self._updating_selection:
            return
        
        model, paths = selection.get_selected_rows()
        
        # Get currently visible selected PIDs
        visible_selected = set()
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, pid_column)
            name = model.get_value(iter, 0)
            cpu_str = model.get_value(iter, 1)  # e.g., "5.2%"
            mem_str = model.get_value(iter, 2)  # e.g., "150.5 MiB"
            user = model.get_value(iter, user_column) if user_column is not None else ""
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
        for row in list_store:
            visible_pids.add(row[pid_column])
        
        # Remove deselected PIDs (only those that are visible and not selected)
        pids_to_remove = []
        for pid in self.selected_pids:
            if pid in visible_pids and pid not in visible_selected:
                pids_to_remove.append(pid)
        
        for pid in pids_to_remove:
            del self.selected_pids[pid]
        
        # Update the selection panel for current tab
        self.update_selection_panel()
    
    def _build_process_tree(self, processes):
        """Build a tree structure from processes based on parent-child relationships.
        
        Returns:
            Dict mapping PID to dict with 'proc' (process data) and 'children' (list of child PIDs)
        """
        # Create process map
        process_map = {proc['pid']: proc for proc in processes}
        
        # Build tree structure
        tree = {}
        roots = []
        
        for proc in processes:
            pid = proc['pid']
            ppid = proc.get('ppid', 1)
            
            if pid not in tree:
                tree[pid] = {'proc': proc, 'children': []}
            
            # If parent exists in our process list, add as child
            if ppid in process_map and ppid != pid:
                if ppid not in tree:
                    tree[ppid] = {'proc': process_map[ppid], 'children': []}
                tree[ppid]['children'].append(pid)
            else:
                # Root process (no parent in our list or parent is init/systemd)
                roots.append(pid)
        
        return {'tree': tree, 'roots': roots}
    
    def _populate_tree_store(self, tree_store, parent_iter, tree_data, io_stats_map=None):
        """Populate tree store with process tree data.
        
        Args:
            tree_store: The Gtk.TreeStore to populate.
            parent_iter: Parent iterator or None for root level.
            tree_data: Tree data from _build_process_tree.
            io_stats_map: Optional dict mapping PID to I/O stats.
        """
        tree = tree_data['tree']
        roots = tree_data['roots']
        io_stats_map = io_stats_map or {}
        
        # Sort roots by PID for consistent ordering
        roots.sort()
        
        for root_pid in roots:
            self._add_tree_node(tree_store, parent_iter, tree, root_pid, io_stats_map)
    
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
        
        io_stats_map = io_stats_map or {}
        node = tree[pid]
        proc = node['proc']
        
        # Get I/O stats for this process
        io_data = io_stats_map.get(pid, {})
        read_rate = io_data.get('read_bytes_per_sec', 0)
        write_rate = io_data.get('write_bytes_per_sec', 0)
        
        # Add this node
        iter = tree_store.append(parent_iter, [
            proc['name'],
            f"{proc['cpu']:.1f}%",
            self.format_memory(proc['memory']),
            proc['started'],
            proc['user'],
            str(proc['nice']),
            proc['pid'],
            self.format_rate(read_rate),
            self.format_rate(write_rate),
        ])
        
        # Add children (sorted by PID)
        children = sorted(node['children'])
        for child_pid in children:
            self._add_tree_node(tree_store, iter, tree, child_pid, io_stats_map)
    
    def _restore_tree_selection(self, tree_store, parent_iter, selection):
        """Restore selection in tree view by PID."""
        iter = tree_store.iter_children(parent_iter) if parent_iter else tree_store.get_iter_first()
        
        while iter:
            pid = tree_store.get_value(iter, 6)  # PID column
            path = tree_store.get_path(iter)
            
            if pid in self.selected_pids:
                selection.select_path(path)
            
            # Check children
            child_iter = tree_store.iter_children(iter)
            if child_iter:
                self._restore_tree_selection(tree_store, iter, selection)
            
            iter = tree_store.iter_next(iter)
    
    def _recreate_tree_view(self):
        """Recreate the process view with tree store for tree view mode."""
        # Get current scrolled window
        scrolled = self.tree_view.get_parent()
        if scrolled:
            scrolled.set_child(None)
        
        # Create tree store with I/O columns
        self.tree_store = Gtk.TreeStore(str, str, str, str, str, str, int, str, str)
        self.list_store = self.tree_store  # Use tree_store as list_store for compatibility
        
        # Reattach sort functions to the new store
        self._attach_sort_functions(self.tree_store)
        
        # Update tree view to use tree store
        self.tree_view.set_model(self.tree_store)
        self.tree_view.set_show_expanders(True)
        self.tree_view.set_level_indentation(20)
        
        if scrolled:
            scrolled.set_child(self.tree_view)
    
    def _recreate_list_view(self):
        """Recreate the process view with list store for flat view mode."""
        # Get current scrolled window
        scrolled = self.tree_view.get_parent()
        if scrolled:
            scrolled.set_child(None)
        
        # Create list store with I/O columns
        self.list_store = Gtk.ListStore(str, str, str, str, str, str, int, str, str)
        
        # Reattach sort functions to the new store
        self._attach_sort_functions(self.list_store)
        
        # Update tree view to use list store
        self.tree_view.set_model(self.list_store)
        self.tree_view.set_show_expanders(False)
        
        if scrolled:
            scrolled.set_child(self.tree_view)
    
    def refresh_processes(self):
        """Refresh the process list."""
        # Only refresh if we're on the processes tab
        if self.current_tab != 'processes':
            return
        
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
        
        # Get filtered processes
        processes = self.process_manager.get_processes(
            show_all=show_all,
            my_processes=my_processes,
            active_only=False,
            show_kernel_threads=show_kernel_threads
        )
        
        # Filter by search
        if search_text:
            search_lower = search_text.lower()
            
            def matches_search(proc):
                """Check if process matches search text."""
                return (search_lower in proc['name'].lower() or
                       search_lower in str(proc['pid']) or
                       search_lower in proc['user'].lower())
            
            # When searching, hide already selected items from results
            filtered_processes = [p for p in processes if 
                        matches_search(p) and
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
        
        # Get I/O stats for all processes
        all_pids_list = [p['pid'] for p in filtered_processes]
        io_stats_map = self.io_stats.get_all_processes_io(all_pids_list)
        
        # Update list store or tree store based on mode
        self._updating_selection = True
        tree_view_mode = self.settings.get("tree_view_mode", False)
        
        if tree_view_mode:
            # Use tree store for tree view
            if not hasattr(self, 'tree_store') or not isinstance(self.list_store, Gtk.TreeStore):
                # Recreate view with tree store
                self._recreate_tree_view()
            
            self.tree_store.clear()
            # Build tree structure
            tree_data = self._build_process_tree(filtered_processes)
            self._populate_tree_store(self.tree_store, None, tree_data, io_stats_map)
        else:
            # Use list store for flat view
            if not isinstance(self.list_store, Gtk.ListStore):
                # Recreate view with list store
                self._recreate_list_view()
            
            self.list_store.clear()
            for proc in filtered_processes:
                # Get I/O stats for this process
                io_data = io_stats_map.get(proc['pid'], {})
                read_rate = io_data.get('read_bytes_per_sec', 0)
                write_rate = io_data.get('write_bytes_per_sec', 0)
                
                self.list_store.append([
                    proc['name'],
                    f"{proc['cpu']:.1f}%",
                    self.format_memory(proc['memory']),
                    proc['started'],
                    proc['user'],
                    str(proc['nice']),
                    proc['pid'],
                    self.format_rate(read_rate),
                    self.format_rate(write_rate),
                ])
        
        # Restore selection by PID from persistent selection
        selection = self.tree_view.get_selection()
        if self.selected_pids:
            if tree_view_mode:
                # Restore selection in tree view
                self._restore_tree_selection(self.tree_store, None, selection)
            else:
                # Restore selection in list view
                for i, row in enumerate(self.list_store):
                    if row[6] in self.selected_pids:  # PID column
                        selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        self._updating_selection = False
        
        # Update the selection panel (in case processes were cleaned up)
        self.update_selection_panel()
        
        # Update bookmarks panel
        self.update_bookmarks_panel()
        
        # Update high usage panel
        self.update_high_usage_panel(all_processes)
        
        # Update process history
        if self.process_history:
            self.process_history.update_processes(all_processes)
    
    
    
    def format_memory(self, bytes_val):
        """Format memory in human-readable format."""
        if bytes_val >= 1024 ** 3:
            return f"{bytes_val / (1024 ** 3):.1f} GiB"
        elif bytes_val >= 1024 ** 2:
            return f"{bytes_val / (1024 ** 2):.1f} MiB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.1f} KiB"
        return f"{bytes_val} B"
    
    def format_rate(self, bytes_per_sec):
        """Format I/O rate in human-readable format with /s suffix."""
        if bytes_per_sec <= 0:
            return "-"
        if bytes_per_sec >= 1024 ** 3:
            return f"{bytes_per_sec / (1024 ** 3):.1f} GiB/s"
        elif bytes_per_sec >= 1024 ** 2:
            return f"{bytes_per_sec / (1024 ** 2):.1f} MiB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KiB/s"
        return f"{bytes_per_sec:.0f} B/s"
    
    def format_bytes(self, bytes_val):
        """Format bytes in human-readable format (same as format_memory but can handle float rates)."""
        if bytes_val >= 1024 ** 3:
            return f"{bytes_val / (1024 ** 3):.2f} GiB"
        elif bytes_val >= 1024 ** 2:
            return f"{bytes_val / (1024 ** 2):.2f} MiB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.2f} KiB"
        elif bytes_val >= 1:
            return f"{bytes_val:.0f} B"
        return f"{bytes_val:.2f} B"
    
    def update_system_stats(self):
        """Update system CPU, memory, swap, disk, and GPU stats."""
        # CPU
        cpu_stats = self.system_stats.get_cpu_usage()
        self.cpu_percent = cpu_stats.get('cpu_usage', 0)
        self.cpu_details.set_text(f"{self.cpu_percent:.1f}%")
        
        # Load average
        load_avg = self.system_stats.get_load_average()
        self.cpu_load.set_text(f"Load: {load_avg['1min']:.2f}")
        self.cpu_indicator.queue_draw()
        
        # Memory
        stats = self.system_stats.get_memory_info()
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
        
        # GPU stats (only update when on GPU tab)
        if self.current_tab == 'gpu':
            gpu_stats = self.gpu_stats.get_total_gpu_stats()
            self.gpu_percent = gpu_stats.get('total_gpu_usage', 0)
            self.gpu_encoding_percent = gpu_stats.get('total_encoding', 0)
            self.gpu_decoding_percent = gpu_stats.get('total_decoding', 0)
            
            self.gpu_details.set_text(f"{self.gpu_percent:.1f}%")
            self.gpu_enc_dec.set_text(
                f"Enc: {self.gpu_encoding_percent:.1f}% | Dec: {self.gpu_decoding_percent:.1f}%"
            )
            self.gpu_indicator.queue_draw()
            
            # Show GPU stats section
            self.gpu_stats_section.set_visible(True)
            self.gpu_stats_sep.set_visible(True)
        else:
            # Hide GPU stats section when not on GPU tab
            self.gpu_stats_section.set_visible(False)
            self.gpu_stats_sep.set_visible(False)
        
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
    
    def select_first_item(self):
        """Select the first item in the process list."""
        if len(self.list_store) > 0 and not self.selected_pids:
            selection = self.tree_view.get_selection()
            selection.select_path(Gtk.TreePath.new_first())
        return False  # Don't repeat
    
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
        
        # Handle Escape key to close search bar
        if keyval == Gdk.KEY_Escape:
            if self.search_bar.get_search_mode():
                self.search_entry.set_text("")
                self.search_bar.set_search_mode(False)
                # Focus current tab's tree view
                tree_view, _, _ = self._get_current_tree_view_info()
                tree_view.grab_focus()
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
            GLib.timeout_add(500, self._refresh_current_tab)
    
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
        
        GLib.timeout_add(500, self._refresh_current_tab)
    
    def on_kill_process(self, button):
        """Kill selected process(es)."""
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
            processes.append({'pid': pid, 'name': name})
        
        if self.settings.get("confirm_kill"):
            self.show_termination_dialog(processes)
        else:
            self.kill_processes_direct([p['pid'] for p in processes])
    
    def show_termination_dialog(self, processes):
        """Show termination dialog with status tracking."""
        dialog = TerminationDialog(self, self.process_manager, processes)
        dialog.present()
    
    def show_shortcuts(self):
        """Show keyboard shortcuts window."""
        shortcuts_window = ShortcutsWindow(self)
        shortcuts_window.present()
    
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
        GLib.timeout_add(500, self._refresh_current_tab)
    
    def show_error(self, message):
        """Show error toast."""
        toast = Adw.Toast(title=message, timeout=3)
        self.toast_overlay.add_toast(toast)
    
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
    
    def send_signal_to_selected(self, sig):
        """Send a specific signal to all selected processes.
        
        Args:
            sig: The signal to send (e.g., signal.SIGSTOP).
        """
        if not self.selected_pids:
            return
        
        success_count = 0
        error_count = 0
        
        for pid in list(self.selected_pids.keys()):
            try:
                self.process_manager.kill_process(pid, sig)
                success_count += 1
            except Exception as e:
                error_count += 1
        
        # Show toast with result
        signal_name = {
            signal.SIGSTOP: "SIGSTOP",
            signal.SIGCONT: "SIGCONT",
            signal.SIGHUP: "SIGHUP",
            signal.SIGINT: "SIGINT",
        }.get(sig, str(sig))
        
        if error_count == 0:
            message = f"Sent {signal_name} to {success_count} process(es)"
        else:
            message = f"Sent {signal_name} to {success_count} process(es), {error_count} failed"
        
        toast = Adw.Toast(title=message, timeout=3)
        self.toast_overlay.add_toast(toast)
        
        # Refresh the process list
        GLib.timeout_add(500, self._refresh_current_tab)
    
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
    
