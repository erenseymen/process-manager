# SPDX-License-Identifier: GPL-3.0-or-later
# Ports tab mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk

from ..dialogs import ProcessDetailsDialog, TerminationDialog


class PortsTabMixin:
    """Mixin class providing Ports tab functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - port_stats: PortStats instance
    - process_manager: ProcessManager instance
    - settings: Settings instance
    - current_tab: str
    - view_stack: Adw.ViewStack
    - auto_refresh_button: Gtk.ToggleButton
    - selected_pids: dict
    - format_memory: method
    - format_bytes: method
    """
    
    def create_ports_tab(self):
        """Create the ports tab content."""
        tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Ports list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.ports_view = self.create_ports_view()
        scrolled.set_child(self.ports_view)
        tab_box.append(scrolled)
        
        return tab_box
    
    def create_ports_view(self):
        """Create the ports list view."""
        # Create list store: name, pid, protocol, local_address, local_port, remote_address, remote_port, state,
        # bytes_sent, bytes_recv, bytes_sent_rate, bytes_recv_rate
        self.ports_list_store = Gtk.ListStore(str, int, str, str, int, str, int, str, str, str, str, str)
        
        # Create tree view
        tree_view = Gtk.TreeView(model=self.ports_list_store)
        tree_view.set_headers_clickable(True)
        tree_view.set_enable_search(False)
        tree_view.set_search_column(-1)  # Disable search completely
        
        # Selection
        selection = tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        
        # Right-click context menu
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self.on_ports_right_click)
        tree_view.add_controller(gesture)
        
        # Key controller for tree view
        tree_key_controller = Gtk.EventControllerKey()
        tree_key_controller.connect("key-pressed", self.on_ports_tree_view_key_pressed)
        tree_view.add_controller(tree_key_controller)
        
        # Columns
        columns = [
            ("Process Name", 0, 200),
            ("PID", 1, 80),
            ("Protocol", 2, 80),
            ("Local Address", 3, 150),
            ("Local Port", 4, 100),
            ("Remote Address", 5, 150),
            ("Remote Port", 6, 100),
            ("State", 7, 100),
            ("Sent", 8, 100),
            ("Received", 9, 100),
            ("Sent/s", 10, 100),
            ("Recv/s", 11, 100),
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
            
            # Right-align numeric columns
            if col_id in [8, 9, 10, 11]:  # Traffic columns
                renderer.set_property("xalign", 1.0)
            
            tree_view.append_column(column)
        
        # Custom sorting for numeric columns
        self.ports_list_store.set_sort_func(1, self.sort_pid, None)  # PID
        self.ports_list_store.set_sort_func(4, self.sort_local_port, None)  # Local Port
        self.ports_list_store.set_sort_func(6, self.sort_remote_port, None)  # Remote Port
        self.ports_list_store.set_sort_func(8, self.sort_bytes, 8)  # Bytes Sent
        self.ports_list_store.set_sort_func(9, self.sort_bytes, 9)  # Bytes Received
        self.ports_list_store.set_sort_func(10, self.sort_bytes_rate, 10)  # Sent/s
        self.ports_list_store.set_sort_func(11, self.sort_bytes_rate, 11)  # Recv/s
        
        # Default sort by local port
        self.ports_list_store.set_sort_column_id(4, Gtk.SortType.ASCENDING)
        
        self.ports_tree_view = tree_view
        return tree_view
    
    def sort_local_port(self, model, iter1, iter2, user_data):
        """Sort by local port number."""
        val1 = model.get_value(iter1, 4)  # Local port column
        val2 = model.get_value(iter2, 4)
        return (val1 > val2) - (val1 < val2)
    
    def sort_remote_port(self, model, iter1, iter2, user_data):
        """Sort by remote port number."""
        val1 = model.get_value(iter1, 6)  # Remote port column
        val2 = model.get_value(iter2, 6)
        # Handle 0 values (for ports without remote connection)
        if val1 == 0:
            val1 = -1  # Put unconnected ports at the end
        if val2 == 0:
            val2 = -1
        return (val1 > val2) - (val1 < val2)
    
    def sort_bytes(self, model, iter1, iter2, user_data):
        """Sort by bytes value (formatted string like '1.2 MiB')."""
        def parse_bytes(s):
            """Parse formatted bytes string to numeric value."""
            if not s or s == '-':
                return 0
            s = s.strip()
            try:
                if s.endswith('TiB'):
                    return float(s[:-3]) * 1024 ** 4
                elif s.endswith('GiB'):
                    return float(s[:-3]) * 1024 ** 3
                elif s.endswith('MiB'):
                    return float(s[:-3]) * 1024 ** 2
                elif s.endswith('KiB'):
                    return float(s[:-3]) * 1024
                elif s.endswith('B'):
                    return float(s[:-1])
                else:
                    return float(s)
            except ValueError:
                return 0
        
        val1 = parse_bytes(model.get_value(iter1, user_data))
        val2 = parse_bytes(model.get_value(iter2, user_data))
        return (val2 > val1) - (val2 < val1)  # Descending by default
    
    def sort_bytes_rate(self, model, iter1, iter2, user_data):
        """Sort by bytes rate (formatted string like '1.2 MiB/s')."""
        def parse_rate(s):
            """Parse formatted rate string to numeric value."""
            if not s or s == '-':
                return 0
            s = s.strip().rstrip('/s')
            try:
                if s.endswith('TiB'):
                    return float(s[:-3]) * 1024 ** 4
                elif s.endswith('GiB'):
                    return float(s[:-3]) * 1024 ** 3
                elif s.endswith('MiB'):
                    return float(s[:-3]) * 1024 ** 2
                elif s.endswith('KiB'):
                    return float(s[:-3]) * 1024
                elif s.endswith('B'):
                    return float(s[:-1])
                else:
                    return float(s)
            except ValueError:
                return 0
        
        val1 = parse_rate(model.get_value(iter1, user_data))
        val2 = parse_rate(model.get_value(iter2, user_data))
        return (val2 > val1) - (val2 < val1)  # Descending by default
    
    def refresh_ports(self):
        """Refresh the ports list."""
        # Only refresh if we're on the ports tab
        if self.current_tab != 'ports':
            return
        
        # Get search text
        search_text = self.search_entry.get_text().lower()
        
        # Get all open ports
        ports = self.port_stats.get_open_ports()
        
        # Filter by search text if provided
        if search_text:
            filtered_ports = []
            for port in ports:
                if (search_text in (port.get('name') or '').lower() or
                    search_text in str(port.get('pid', '')) or
                    search_text in str(port.get('local_port', '')) or
                    search_text in (port.get('protocol', '')).lower() or
                    search_text in (port.get('local_address', '')).lower()):
                    filtered_ports.append(port)
            ports = filtered_ports
        
        # Check if grouping is enabled
        group_processes_mode = self.settings.get("group_processes_mode", False)
        
        # Update ports list store
        self.ports_list_store.clear()
        
        if group_processes_mode:
            # Group ports by PID
            grouped_by_pid = {}
            for port in ports:
                pid = port.get('pid') or 0
                if pid not in grouped_by_pid:
                    grouped_by_pid[pid] = {
                        'name': port.get('name') or 'N/A',
                        'pid': pid,
                        'ports': [],
                        'total_bytes_sent': 0,
                        'total_bytes_recv': 0,
                        'total_bytes_sent_rate': 0.0,
                        'total_bytes_recv_rate': 0.0,
                    }
                
                grouped_by_pid[pid]['ports'].append(port)
                grouped_by_pid[pid]['total_bytes_sent'] += port.get('bytes_sent', 0)
                grouped_by_pid[pid]['total_bytes_recv'] += port.get('bytes_recv', 0)
                grouped_by_pid[pid]['total_bytes_sent_rate'] += port.get('bytes_sent_rate', 0.0)
                grouped_by_pid[pid]['total_bytes_recv_rate'] += port.get('bytes_recv_rate', 0.0)
            
            # Add grouped entries to list store
            for pid, group_data in grouped_by_pid.items():
                num_ports = len(group_data['ports'])
                
                # Get unique protocols and states
                protocols = set()
                states = set()
                local_addresses = set()
                local_ports = set()
                
                for port in group_data['ports']:
                    protocols.add(port.get('protocol', 'N/A'))
                    states.add(port.get('state', 'N/A'))
                    local_addresses.add(port.get('local_address', 'N/A'))
                    local_ports.add(str(port.get('local_port', 0)))
                
                # Format combined information
                protocol_str = ', '.join(sorted(protocols)) if protocols else 'N/A'
                if len(protocol_str) > 50:
                    protocol_str = f"{len(protocols)} protocols"
                
                state_str = ', '.join(sorted(states)) if states else 'N/A'
                if len(state_str) > 50:
                    state_str = f"{len(states)} states"
                
                local_addr_str = f"{len(local_addresses)} addresses" if len(local_addresses) > 1 else (list(local_addresses)[0] if local_addresses else 'N/A')
                
                # Get local port value (use first port number if multiple, or 0)
                local_port_value = 0
                if local_ports:
                    # Try to get first port number
                    first_port_str = list(local_ports)[0]
                    try:
                        local_port_value = int(first_port_str)
                    except (ValueError, TypeError):
                        local_port_value = 0
                
                # Format traffic statistics
                total_bytes_sent = group_data['total_bytes_sent']
                total_bytes_recv = group_data['total_bytes_recv']
                total_bytes_sent_rate = group_data['total_bytes_sent_rate']
                total_bytes_recv_rate = group_data['total_bytes_recv_rate']
                
                bytes_sent_str = self.format_bytes(total_bytes_sent) if total_bytes_sent > 0 else '-'
                bytes_recv_str = self.format_bytes(total_bytes_recv) if total_bytes_recv > 0 else '-'
                bytes_sent_rate_str = f"{self.format_bytes(total_bytes_sent_rate)}/s" if total_bytes_sent_rate > 0 else '-'
                bytes_recv_rate_str = f"{self.format_bytes(total_bytes_recv_rate)}/s" if total_bytes_recv_rate > 0 else '-'
                
                # Show connection count in remote address column
                remote_addr_str = f"{num_ports} connection{'s' if num_ports > 1 else ''}"
                remote_port_str = '-'
                
                self.ports_list_store.append([
                    group_data['name'],
                    pid,
                    protocol_str,
                    local_addr_str,
                    local_port_value,
                    remote_addr_str,
                    0,  # Remote port - not applicable for grouped view
                    state_str,
                    bytes_sent_str,
                    bytes_recv_str,
                    bytes_sent_rate_str,
                    bytes_recv_rate_str
                ])
        else:
            # Normal mode - show individual ports
            for port in ports:
                # Format remote address/port
                remote_addr = port.get('remote_address') or '-'
                remote_port = port.get('remote_port')
                remote_port_str = str(remote_port) if remote_port is not None else '-'
                
                # Format traffic statistics
                bytes_sent = port.get('bytes_sent', 0)
                bytes_recv = port.get('bytes_recv', 0)
                bytes_sent_rate = port.get('bytes_sent_rate', 0.0)
                bytes_recv_rate = port.get('bytes_recv_rate', 0.0)
                
                bytes_sent_str = self.format_bytes(bytes_sent) if bytes_sent > 0 else '-'
                bytes_recv_str = self.format_bytes(bytes_recv) if bytes_recv > 0 else '-'
                bytes_sent_rate_str = f"{self.format_bytes(bytes_sent_rate)}/s" if bytes_sent_rate > 0 else '-'
                bytes_recv_rate_str = f"{self.format_bytes(bytes_recv_rate)}/s" if bytes_recv_rate > 0 else '-'
                
                self.ports_list_store.append([
                    port.get('name') or 'N/A',
                    port.get('pid') or 0,
                    port.get('protocol', 'N/A'),
                    port.get('local_address', 'N/A'),
                    port.get('local_port', 0),
                    remote_addr,
                    remote_port if remote_port is not None else 0,
                    port.get('state', 'N/A'),
                    bytes_sent_str,
                    bytes_recv_str,
                    bytes_sent_rate_str,
                    bytes_recv_rate_str
                ])
    
    def on_ports_right_click(self, gesture, n_press, x, y):
        """Handle right-click context menu for ports tab."""
        # Get clicked row
        path_info = self.ports_tree_view.get_path_at_pos(int(x), int(y))
        if path_info:
            path, column, cell_x, cell_y = path_info
            selection = self.ports_tree_view.get_selection()
            selection.unselect_all()
            selection.select_path(path)
            
            # Show context menu
            self._show_ports_context_menu(x, y)
    
    def _show_ports_context_menu(self, x, y):
        """Show the ports context menu."""
        # Get selected PID
        selection = self.ports_tree_view.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            return
        
        path = paths[0]
        iter = model.get_iter(path)
        pid = model.get_value(iter, 1)  # PID column
        
        if pid == 0:
            return  # No process associated
        
        # Create a simple popover menu
        popover = Gtk.PopoverMenu()
        popover.set_parent(self.ports_tree_view)
        
        # Create menu model
        menu = Gio.Menu()
        
        # Show Process Details action
        details_action = Gio.SimpleAction.new("ports-context-details", None)
        details_action.connect("activate", lambda a, p: self._show_port_process_details(pid))
        self.add_action(details_action)
        menu.append("Show Process Details", "win.ports-context-details")
        
        # End Process action
        end_action = Gio.SimpleAction.new("ports-context-kill", None)
        end_action.connect("activate", lambda a, p: self._kill_port_process(pid))
        self.add_action(end_action)
        menu.append("End Process", "win.ports-context-kill")
        
        popover.set_menu_model(menu)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()
    
    def _show_port_process_details(self, pid):
        """Show process details for a port's process."""
        try:
            # Get process info
            all_processes = self.process_manager.get_processes(
                show_all=True,
                my_processes=False,
                active_only=False,
                show_kernel_threads=True
            )
            process_map = {p['pid']: p for p in all_processes}
            
            if pid not in process_map:
                return
            
            proc = process_map[pid]
            process_info = {
                'name': proc['name'],
                'cpu_str': f"{proc['cpu']:.1f}%",
                'mem_str': self.format_memory(proc['memory']),
                'user': proc['user'],
                'state': proc['state'],
                'nice': proc['nice'],
                'started': proc['started']
            }
            
            dialog = ProcessDetailsDialog(self, self.process_manager, pid, process_info)
            dialog.present()
        except Exception:
            pass
    
    def _kill_port_process(self, pid):
        """Kill a process from the ports tab."""
        try:
            all_processes = self.process_manager.get_processes(
                show_all=True,
                my_processes=False,
                active_only=False,
                show_kernel_threads=True
            )
            process_map = {p['pid']: p for p in all_processes}
            
            if pid not in process_map:
                return
            
            proc = process_map[pid]
            processes = [{'pid': pid, 'name': proc['name']}]
            dialog = TerminationDialog(self, self.process_manager, processes)
            dialog.present()
        except Exception:
            pass
    
    def on_ports_tree_view_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events in ports tree view."""
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
        
        # Handle Space - toggle Play/Pause auto refresh
        if keyval == Gdk.KEY_space and not has_ctrl and not has_alt and not has_shift:
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
        
        # Enter key - show process details
        if (keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter) and not has_ctrl and not has_alt and not has_shift:
            selection = self.ports_tree_view.get_selection()
            model, paths = selection.get_selected_rows()
            if paths:
                path = paths[0]
                iter = model.get_iter(path)
                pid = model.get_value(iter, 1)  # PID column
                if pid != 0:
                    self._show_port_process_details(pid)
            return True
        return False

