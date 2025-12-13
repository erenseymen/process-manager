# SPDX-License-Identifier: GPL-3.0-or-later
# Selection panel mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Pango


class SelectionPanelMixin:
    """Mixin class providing selection panel functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - selected_pids: dict of selected PIDs
    - current_tab: str
    - settings: Settings instance
    - format_memory: method
    - format_bytes: method
    - parse_cpu_str: method
    - parse_mem_str: method
    - on_kill_process: method
    - _get_current_tree_view_info: method
    - _updating_selection: bool flag
    """
    
    def _create_selection_panel_ui(self):
        """Create the UI elements for a selection panel."""
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
        
        return panel_box, title_label, selection_list

    def create_selection_panel_for_tab(self, tab_name):
        """Create a selection panel for a specific tab (reuses the same selected_pids)."""
        panel_box, title_label, selection_list = self._create_selection_panel_ui()
        
        # Store references based on tab
        if tab_name == 'gpu':
            self.gpu_selection_title = title_label
            self.gpu_selection_list = selection_list
        elif tab_name == 'ports':
            self.ports_selection_title = title_label
            self.ports_selection_list = selection_list
        
        return panel_box
    
    def create_selection_panel(self):
        """Create the selection panel showing selected processes grouped by name with comparison bars."""
        panel_box, title_label, selection_list = self._create_selection_panel_ui()
        
        self.selection_title = title_label
        self.selection_list = selection_list
        # We don't need to store button references as they are not used elsewhere
        
        return panel_box
    
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
        
        # Calculate totals based on current tab
        if self.current_tab == 'gpu':
            # GPU tab: show GPU and CPU usage
            total_gpu = sum(info.get('gpu_usage', 0.0) for info in self.selected_pids.values())
            total_cpu = sum(self.parse_cpu_str(info.get('cpu_str', '0%')) 
                           for info in self.selected_pids.values())
            # Update title with totals
            title_label.set_label(
                f"Selected ({count}): GPU {total_gpu:.1f}% | CPU {total_cpu:.1f}%"
            )
        elif self.current_tab == 'ports':
            # Ports tab: show sent and received
            total_sent = sum(info.get('bytes_sent', 0) for info in self.selected_pids.values())
            total_recv = sum(info.get('bytes_recv', 0) for info in self.selected_pids.values())
            # Update title with totals
            title_label.set_label(
                f"Selected ({count}): Sent {self.format_bytes(total_sent)} | Received {self.format_bytes(total_recv)}"
            )
        else:
            # Processes tab: show CPU and Memory
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
                if self.current_tab == 'gpu':
                    groups[name] = {'pids': [], 'gpu': 0.0, 'cpu': 0.0}
                elif self.current_tab == 'ports':
                    groups[name] = {'pids': [], 'sent': 0, 'recv': 0}
                else:
                    groups[name] = {'pids': [], 'cpu': 0.0, 'mem': 0}
            groups[name]['pids'].append(pid)
            if self.current_tab == 'gpu':
                groups[name]['gpu'] += info.get('gpu_usage', 0.0)
                groups[name]['cpu'] += self.parse_cpu_str(info.get('cpu_str', '0%'))
            elif self.current_tab == 'ports':
                groups[name]['sent'] += info.get('bytes_sent', 0)
                groups[name]['recv'] += info.get('bytes_recv', 0)
            else:
                groups[name]['cpu'] += self.parse_cpu_str(info.get('cpu_str', '0%'))
                groups[name]['mem'] += self.parse_mem_str(info.get('mem_str', '0 B'))
        
        # Find max values for relative bar scaling
        if self.current_tab == 'gpu':
            max_gpu = max((g['gpu'] for g in groups.values()), default=1.0) or 1.0
            max_cpu = max((g['cpu'] for g in groups.values()), default=1.0) or 1.0
            # Sort groups by GPU usage (descending) for comparison
            sorted_groups = sorted(groups.items(), key=lambda x: x[1]['gpu'], reverse=True)
        elif self.current_tab == 'ports':
            max_sent = max((g['sent'] for g in groups.values()), default=1) or 1
            max_recv = max((g['recv'] for g in groups.values()), default=1) or 1
            # Sort groups by sent bytes (descending) for comparison
            sorted_groups = sorted(groups.items(), key=lambda x: x[1]['sent'], reverse=True)
        else:
            max_cpu = max((g['cpu'] for g in groups.values()), default=1.0) or 1.0
            max_mem = max((g['mem'] for g in groups.values()), default=1) or 1
            # Sort groups by memory usage (descending) for comparison
            sorted_groups = sorted(groups.items(), key=lambda x: x[1]['mem'], reverse=True)
        
        # Create comparison rows for each group
        for name, group_info in sorted_groups:
            pids = sorted(group_info['pids'])
            if self.current_tab == 'gpu':
                row = self.create_comparison_row(name, pids, group_info['gpu'], group_info['cpu'], max_gpu, max_cpu, tab_type='gpu')
            elif self.current_tab == 'ports':
                row = self.create_comparison_row(name, pids, group_info['sent'], group_info['recv'], max_sent, max_recv, tab_type='ports')
            else:
                row = self.create_comparison_row(name, pids, group_info['cpu'], group_info['mem'], max_cpu, max_mem, tab_type='processes')
            selection_list.append(row)
    
    def create_comparison_row(self, name, pids, value1, value2, max_value1, max_value2, tab_type='processes'):
        """Create a comparison row widget for a selected process group with bars.
        
        Args:
            name: Process name
            pids: List of PIDs
            value1: First value (CPU for processes/gpu, GPU for gpu tab, Sent for ports)
            value2: Second value (Memory for processes, CPU for gpu tab, Received for ports)
            max_value1: Maximum value1 for scaling
            max_value2: Maximum value2 for scaling
            tab_type: 'processes', 'gpu', or 'ports'
        """
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
        
        if tab_type == 'gpu':
            # GPU tab: GPU bar (primary) and CPU bar
            self._create_gpu_comparison_bars(bars_box, value1, value2, max_value1, max_value2)
        elif tab_type == 'ports':
            # Ports tab: Sent bar (primary) and Received bar
            self._create_ports_comparison_bars(bars_box, value1, value2, max_value1, max_value2)
        else:
            # Processes tab: Memory bar (primary) and CPU bar
            self._create_processes_comparison_bars(bars_box, value1, value2, max_value1, max_value2)
        
        row_box.append(bars_box)
        
        return row_box
    
    def _create_gpu_comparison_bars(self, bars_box, gpu_value, cpu_value, max_gpu, max_cpu):
        """Create GPU and CPU comparison bars."""
        # GPU bar
        gpu_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        gpu_label = Gtk.Label(label="GPU")
        gpu_label.add_css_class("bar-label")
        gpu_label.set_width_chars(4)
        gpu_label.set_xalign(0)
        gpu_bar_box.append(gpu_label)
        
        gpu_fraction = (gpu_value / max_gpu) if max_gpu > 0 else 0
        gpu_bar = Gtk.ProgressBar()
        gpu_bar.set_fraction(gpu_fraction)
        gpu_bar.set_hexpand(True)
        gpu_bar.add_css_class("comparison-gpu-bar")
        # Add color class based on absolute GPU usage
        if gpu_value > 50:
            gpu_bar.add_css_class("bar-high")
        elif gpu_value > 10:
            gpu_bar.add_css_class("bar-medium")
        else:
            gpu_bar.add_css_class("bar-low")
        gpu_bar_box.append(gpu_bar)
        
        gpu_value_label = Gtk.Label(label=f"{gpu_value:.1f}%")
        gpu_value_label.add_css_class("bar-value")
        gpu_value_label.set_width_chars(10)
        gpu_value_label.set_xalign(1)
        gpu_bar_box.append(gpu_value_label)
        
        bars_box.append(gpu_bar_box)
        
        # CPU bar
        cpu_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        cpu_label = Gtk.Label(label="CPU")
        cpu_label.add_css_class("bar-label")
        cpu_label.set_width_chars(4)
        cpu_label.set_xalign(0)
        cpu_bar_box.append(cpu_label)
        
        cpu_fraction = (cpu_value / max_cpu) if max_cpu > 0 else 0
        cpu_bar = Gtk.ProgressBar()
        cpu_bar.set_fraction(cpu_fraction)
        cpu_bar.set_hexpand(True)
        cpu_bar.add_css_class("comparison-cpu-bar")
        # Add color class based on absolute CPU usage
        if cpu_value > 50:
            cpu_bar.add_css_class("bar-high")
        elif cpu_value > 10:
            cpu_bar.add_css_class("bar-medium")
        else:
            cpu_bar.add_css_class("bar-low")
        cpu_bar_box.append(cpu_bar)
        
        cpu_value_label = Gtk.Label(label=f"{cpu_value:.1f}%")
        cpu_value_label.add_css_class("bar-value")
        cpu_value_label.set_width_chars(10)
        cpu_value_label.set_xalign(1)
        cpu_bar_box.append(cpu_value_label)
        
        bars_box.append(cpu_bar_box)
    
    def _create_ports_comparison_bars(self, bars_box, sent_value, recv_value, max_sent, max_recv):
        """Create Sent and Received comparison bars."""
        # Sent bar
        sent_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        sent_label = Gtk.Label(label="Sent")
        sent_label.add_css_class("bar-label")
        sent_label.set_width_chars(4)
        sent_label.set_xalign(0)
        sent_bar_box.append(sent_label)
        
        sent_fraction = (sent_value / max_sent) if max_sent > 0 else 0
        sent_bar = Gtk.ProgressBar()
        sent_bar.set_fraction(sent_fraction)
        sent_bar.set_hexpand(True)
        sent_bar.add_css_class("comparison-sent-bar")
        # Add color class based on absolute sent bytes
        if sent_value > 1024 * 1024 * 1024:  # > 1 GiB
            sent_bar.add_css_class("bar-high")
        elif sent_value > 100 * 1024 * 1024:  # > 100 MiB
            sent_bar.add_css_class("bar-medium")
        else:
            sent_bar.add_css_class("bar-low")
        sent_bar_box.append(sent_bar)
        
        sent_value_label = Gtk.Label(label=self.format_bytes(sent_value))
        sent_value_label.add_css_class("bar-value")
        sent_value_label.set_width_chars(10)
        sent_value_label.set_xalign(1)
        sent_bar_box.append(sent_value_label)
        
        bars_box.append(sent_bar_box)
        
        # Received bar
        recv_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        recv_label = Gtk.Label(label="Recv")
        recv_label.add_css_class("bar-label")
        recv_label.set_width_chars(4)
        recv_label.set_xalign(0)
        recv_bar_box.append(recv_label)
        
        recv_fraction = (recv_value / max_recv) if max_recv > 0 else 0
        recv_bar = Gtk.ProgressBar()
        recv_bar.set_fraction(recv_fraction)
        recv_bar.set_hexpand(True)
        recv_bar.add_css_class("comparison-recv-bar")
        # Add color class based on absolute received bytes
        if recv_value > 1024 * 1024 * 1024:  # > 1 GiB
            recv_bar.add_css_class("bar-high")
        elif recv_value > 100 * 1024 * 1024:  # > 100 MiB
            recv_bar.add_css_class("bar-medium")
        else:
            recv_bar.add_css_class("bar-low")
        recv_bar_box.append(recv_bar)
        
        recv_value_label = Gtk.Label(label=self.format_bytes(recv_value))
        recv_value_label.add_css_class("bar-value")
        recv_value_label.set_width_chars(10)
        recv_value_label.set_xalign(1)
        recv_bar_box.append(recv_value_label)
        
        bars_box.append(recv_bar_box)
    
    def _create_processes_comparison_bars(self, bars_box, cpu_value, mem_value, max_cpu, max_mem):
        """Create Memory and CPU comparison bars for processes tab."""
        # Memory bar
        mem_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        mem_label = Gtk.Label(label="Mem")
        mem_label.add_css_class("bar-label")
        mem_label.set_width_chars(4)
        mem_label.set_xalign(0)
        mem_bar_box.append(mem_label)
        
        mem_fraction = (mem_value / max_mem) if max_mem > 0 else 0
        mem_bar = Gtk.ProgressBar()
        mem_bar.set_fraction(mem_fraction)
        mem_bar.set_hexpand(True)
        mem_bar.add_css_class("comparison-mem-bar")
        # Add color class based on absolute memory usage
        if mem_value > 1024 * 1024 * 1024:  # > 1 GiB
            mem_bar.add_css_class("bar-high")
        elif mem_value > 256 * 1024 * 1024:  # > 256 MiB
            mem_bar.add_css_class("bar-medium")
        else:
            mem_bar.add_css_class("bar-low")
        mem_bar_box.append(mem_bar)
        
        mem_value_label = Gtk.Label(label=self.format_memory(mem_value))
        mem_value_label.add_css_class("bar-value")
        mem_value_label.set_width_chars(10)
        mem_value_label.set_xalign(1)
        mem_bar_box.append(mem_value_label)
        
        bars_box.append(mem_bar_box)
        
        # CPU bar
        cpu_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        cpu_label = Gtk.Label(label="CPU")
        cpu_label.add_css_class("bar-label")
        cpu_label.set_width_chars(4)
        cpu_label.set_xalign(0)
        cpu_bar_box.append(cpu_label)
        
        cpu_fraction = (cpu_value / max_cpu) if max_cpu > 0 else 0
        cpu_bar = Gtk.ProgressBar()
        cpu_bar.set_fraction(cpu_fraction)
        cpu_bar.set_hexpand(True)
        cpu_bar.add_css_class("comparison-cpu-bar")
        # Add color class based on absolute CPU usage
        if cpu_value > 50:
            cpu_bar.add_css_class("bar-high")
        elif cpu_value > 10:
            cpu_bar.add_css_class("bar-medium")
        else:
            cpu_bar.add_css_class("bar-low")
        cpu_bar_box.append(cpu_bar)
        
        cpu_value_label = Gtk.Label(label=f"{cpu_value:.1f}%")
        cpu_value_label.add_css_class("bar-value")
        cpu_value_label.set_width_chars(10)
        cpu_value_label.set_xalign(1)
        cpu_bar_box.append(cpu_value_label)
        
        bars_box.append(cpu_bar_box)
    
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
        # Also clear ports selection tracking
        if hasattr(self, 'selected_port_keys'):
            self.selected_port_keys.clear()
        self.update_selection_panel()
        # Update tree view selection for all tabs
        self._updating_selection = True
        self.tree_view.get_selection().unselect_all()
        if hasattr(self, 'gpu_tree_view'):
            self.gpu_tree_view.get_selection().unselect_all()
        if hasattr(self, 'ports_tree_view'):
            self.ports_tree_view.get_selection().unselect_all()
        self._updating_selection = False
