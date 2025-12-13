# SPDX-License-Identifier: GPL-3.0-or-later
# High usage panel mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import os
from gi.repository import Gtk, Pango


class HighUsagePanelMixin:
    """Mixin class providing high usage panel functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - settings: Settings instance
    - system_stats: SystemStats instance
    - all_user_button: Gtk.ToggleButton
    - tree_view: Gtk.TreeView
    - list_store: Gtk.ListStore
    - _prev_process_stats: dict
    """
    
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
                return True
        return False
