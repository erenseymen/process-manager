# SPDX-License-Identifier: GPL-3.0-or-later
# Main window

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk
from .process_manager import ProcessManager
from .system_stats import SystemStats


class ProcessManagerWindow(Adw.ApplicationWindow):
    """Main application window."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        app = self.get_application()
        self.settings = app.settings
        self.process_manager = ProcessManager()
        self.system_stats = SystemStats()
        
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
        
        # Kill button
        kill_button = Gtk.Button()
        kill_button.set_icon_name("process-stop-symbolic")
        kill_button.set_tooltip_text("End Process")
        kill_button.add_css_class("destructive-action")
        kill_button.connect("clicked", self.on_kill_process)
        header.pack_start(kill_button)
        
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
        
        # Search bar (always visible)
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_search_mode(True)  # Always visible
        main_box.append(self.search_bar)
        
        # Process list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.process_view = self.create_process_view()
        scrolled.set_child(self.process_view)
        main_box.append(scrolled)
        
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
    
    def create_process_view(self):
        """Create the process list view."""
        # Create list store: name, cpu, memory, started, user, nice, pid
        self.list_store = Gtk.ListStore(str, str, str, str, str, str, int)
        
        # Create tree view
        tree_view = Gtk.TreeView(model=self.list_store)
        tree_view.set_headers_clickable(True)
        tree_view.set_enable_search(True)
        tree_view.set_search_column(0)
        
        # Selection
        selection = tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        
        # Right-click context menu
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self.on_right_click)
        tree_view.add_controller(gesture)
        
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
        self.list_store.set_sort_func(5, self.sort_numeric, None)  # Nice
        self.list_store.set_sort_func(6, self.sort_numeric, None)  # PID
        
        # Default sort by CPU descending
        self.list_store.set_sort_column_id(1, Gtk.SortType.DESCENDING)
        
        self.tree_view = tree_view
        return tree_view
    
    def sort_percent(self, model, iter1, iter2, user_data):
        """Sort by percentage value."""
        val1 = model.get_value(iter1, 1).rstrip('%')
        val2 = model.get_value(iter2, 1).rstrip('%')
        try:
            return (float(val1) > float(val2)) - (float(val1) < float(val2))
        except ValueError:
            return 0
    
    def sort_memory(self, model, iter1, iter2, user_data):
        """Sort by memory value."""
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
        return (val1 > val2) - (val1 < val2)
    
    def sort_numeric(self, model, iter1, iter2, user_data):
        """Sort by numeric value."""
        col = 6  # Default to PID
        val1 = model.get_value(iter1, col)
        val2 = model.get_value(iter2, col)
        return (val1 > val2) - (val1 < val2)
    
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
    
    def refresh_processes(self):
        """Refresh the process list."""
        # Get filter settings from All/User toggle
        show_all = self.all_user_button.get_active()
        my_processes = not show_all
        
        # Get search text
        search_text = self.search_entry.get_text().lower()
        
        # Get processes
        processes = self.process_manager.get_processes(
            show_all=show_all,
            my_processes=my_processes,
            active_only=False
        )
        
        # Filter by search
        if search_text:
            processes = [p for p in processes if search_text in p['name'].lower() or 
                        search_text in str(p['pid']) or
                        search_text in p['user'].lower()]
        
        # Update list store
        self.list_store.clear()
        for proc in processes:
            self.list_store.append([
                proc['name'],
                f"{proc['cpu']:.1f}%",
                self.format_memory(proc['memory']),
                proc['started'],
                proc['user'],
                str(proc['nice']),
                proc['pid']
            ])
    
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
        """Update system memory and swap stats."""
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
    
    def start_refresh_timer(self):
        """Start the auto-refresh timer."""
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
    
    def on_kill_process(self, button):
        """Kill selected process(es)."""
        selection = self.tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return
        
        pids = []
        for path in paths:
            iter = model.get_iter(path)
            pid = model.get_value(iter, 6)
            pids.append(pid)
        
        if self.settings.get("confirm_kill"):
            self.show_kill_confirmation(pids)
        else:
            self.kill_processes(pids)
    
    def show_kill_confirmation(self, pids):
        """Show confirmation dialog before killing processes."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="End Process?",
            body=f"Are you sure you want to end {len(pids)} process(es)?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("kill", "End Process")
        dialog.set_response_appearance("kill", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_kill_response, pids)
        dialog.present()
    
    def on_kill_response(self, dialog, response, pids):
        """Handle kill confirmation response."""
        if response == "kill":
            self.kill_processes(pids)
    
    def kill_processes(self, pids):
        """Kill the specified processes."""
        for pid in pids:
            try:
                self.process_manager.kill_process(pid)
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

