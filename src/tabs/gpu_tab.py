# SPDX-License-Identifier: GPL-3.0-or-later
# GPU tab mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk


class GPUTabMixin:
    """Mixin class providing GPU tab functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - gpu_stats: GPUStats instance
    - process_manager: ProcessManager instance
    - settings: Settings instance
    - selected_pids: dict of selected PIDs
    - _updating_selection: bool flag
    - _gpu_used_pids: set of PIDs that have used GPU
    - toast_overlay: Adw.ToastOverlay
    - current_tab: str
    - format_memory: method
    - update_selection_panel: method
    - _handle_selection_changed: method
    - _handle_right_click: method
    """
    
    # Map column names to column IDs for GPU sort persistence
    GPU_COLUMN_NAME_TO_ID = {
        "name": 0,
        "cpu": 1,
        "memory": 2,
        "pid": 3,
        "started": 4,
        # GPU-specific columns start at 5, but are dynamic based on available GPUs
    }
    GPU_COLUMN_ID_TO_NAME = {v: k for k, v in GPU_COLUMN_NAME_TO_ID.items()}
    
    def on_gpu_sort_column_changed(self, model):
        """Handle GPU sort column change - save to settings."""
        sort_col_id, sort_order = model.get_sort_column_id()
        if sort_col_id is not None and sort_col_id >= 0:
            col_name = self.GPU_COLUMN_ID_TO_NAME.get(sort_col_id, f"gpu_col_{sort_col_id}")
            self.settings.set("gpu_sort_column", col_name)
            self.settings.set("gpu_sort_descending", sort_order == Gtk.SortType.DESCENDING)
    
    def create_gpu_tab(self):
        """Create the GPU tab content."""
        tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Selection panel for GPU tab (shared with processes tab)
        self.gpu_selection_panel = self.create_selection_panel_for_tab('gpu')
        tab_box.append(self.gpu_selection_panel)
        
        # GPU process list
        self.gpu_scrolled = Gtk.ScrolledWindow()
        self.gpu_scrolled.set_vexpand(True)
        self.gpu_scrolled.set_hexpand(True)
        self.gpu_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.gpu_process_view = self.create_gpu_process_view()
        self.gpu_scrolled.set_child(self.gpu_process_view)
        tab_box.append(self.gpu_scrolled)
        
        return tab_box
    
    def create_gpu_process_view(self):
        """Create the GPU process list view."""
        # Determine which GPU columns to show based on available GPUs
        gpu_types = self.gpu_stats.gpu_types
        base_columns = [
            ("Process Name", 0, 200),
            ("CPU %", 1, 80),
            ("Memory", 2, 100),
            ("PID", 3, 80),
            ("Started", 4, 100),
        ]
        
        # Add GPU-specific columns
        gpu_columns = []
        col_id = 5  # Start after base columns (0-4)
        if 'nvidia' in gpu_types:
            gpu_columns.append(("NVIDIA GPU %", col_id, 100))
            col_id += 1
            gpu_columns.append(("NVIDIA Enc %", col_id, 100))
            col_id += 1
            gpu_columns.append(("NVIDIA Dec %", col_id, 100))
            col_id += 1
        if 'intel' in gpu_types:
            gpu_columns.append(("Intel GPU %", col_id, 100))
            col_id += 1
            gpu_columns.append(("Intel Enc %", col_id, 100))
            col_id += 1
            gpu_columns.append(("Intel Dec %", col_id, 100))
            col_id += 1
        if 'amd' in gpu_types:
            gpu_columns.append(("AMD GPU %", col_id, 100))
            col_id += 1
            gpu_columns.append(("AMD Enc %", col_id, 100))
            col_id += 1
            gpu_columns.append(("AMD Dec %", col_id, 100))
            col_id += 1
        
        # Calculate total columns needed (minimum 5 for base columns)
        total_cols = max(5, 5 + len(gpu_columns))
        
        # Create list store with dynamic columns
        # Columns: name, cpu, memory, pid, started, then GPU columns
        col_types = [str] * total_cols
        col_types[3] = int  # PID is int
        self.gpu_list_store = Gtk.ListStore(*col_types)
        
        # Create tree view
        tree_view = Gtk.TreeView(model=self.gpu_list_store)
        tree_view.set_headers_clickable(True)
        tree_view.set_enable_search(False)
        tree_view.set_search_column(-1)  # Disable search completely
        
        # Selection
        selection = tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self.on_gpu_selection_changed)
        
        # Right-click context menu
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self.on_gpu_right_click)
        tree_view.add_controller(gesture)
        
        # Key controller for tree view to handle Space key
        tree_key_controller = Gtk.EventControllerKey()
        tree_key_controller.connect("key-pressed", self.on_tree_view_key_pressed)
        tree_view.add_controller(tree_key_controller)
        
        # Columns
        all_columns = base_columns + gpu_columns
        for i, (title, col_id, width) in enumerate(all_columns):
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
        
        # Store column mapping for GPU data
        self.gpu_column_mapping = {}
        col_idx = 5  # Start after base columns (0-4)
        if 'nvidia' in gpu_types:
            self.gpu_column_mapping['nvidia'] = {
                'gpu': col_idx,
                'enc': col_idx + 1,
                'dec': col_idx + 2
            }
            col_idx += 3
        if 'intel' in gpu_types:
            self.gpu_column_mapping['intel'] = {
                'gpu': col_idx,
                'enc': col_idx + 1,
                'dec': col_idx + 2
            }
            col_idx += 3
        if 'amd' in gpu_types:
            self.gpu_column_mapping['amd'] = {
                'gpu': col_idx,
                'enc': col_idx + 1,
                'dec': col_idx + 2
            }
            col_idx += 3
        
        # Attach sort function for Started column
        self.gpu_list_store.set_sort_func(4, self.sort_gpu_started, None)
        
        # Restore saved sort column and order
        saved_column = self.settings.get("gpu_sort_column")
        saved_descending = self.settings.get("gpu_sort_descending")
        if saved_column:
            # Try to get column ID from name, handling dynamic GPU columns
            if saved_column.startswith("gpu_col_"):
                try:
                    sort_col_id = int(saved_column.split("_")[-1])
                except ValueError:
                    sort_col_id = 0
            else:
                sort_col_id = self.GPU_COLUMN_NAME_TO_ID.get(saved_column, 0)
            sort_order = Gtk.SortType.DESCENDING if saved_descending else Gtk.SortType.ASCENDING
            self.gpu_list_store.set_sort_column_id(sort_col_id, sort_order)
        
        # Connect to sort changes to save them
        self.gpu_list_store.connect("sort-column-changed", self.on_gpu_sort_column_changed)
        
        self.gpu_tree_view = tree_view
        return tree_view
    
    def on_gpu_selection_changed(self, selection):
        """Handle selection changes for GPU tab - sync with persistent selected_pids."""
        self._handle_selection_changed(selection, self.gpu_list_store, pid_column=3, user_column=None)
    
    def sort_gpu_started(self, model, iter1, iter2, user_data):
        """Sort by started time (reversed: newest first on initial click)."""
        val1 = model.get_value(iter1, 4)
        val2 = model.get_value(iter2, 4)
        # Reversed for descending on first click (newest/latest time first)
        return (val2 > val1) - (val2 < val1)
    
    def on_gpu_right_click(self, gesture, n_press, x, y):
        """Handle right-click context menu for GPU tab."""
        self._handle_right_click(self.gpu_tree_view, x, y)
    
    def refresh_gpu_processes(self):
        """Refresh the GPU process list."""
        # Only refresh if we're on the GPU tab
        if self.current_tab != 'gpu':
            return
        
        # Get search text
        search_text = self.search_entry.get_text().lower()
        
        # Get all processes
        all_processes = self.process_manager.get_processes(
            show_all=True,
            my_processes=False,
            active_only=False,
            show_kernel_threads=False
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
        
        # Get GPU process data (only when on GPU tab)
        gpu_processes = self.gpu_stats.get_gpu_processes()
        
        # Update cpu/memory/gpu info for selected processes
        for pid in self.selected_pids:
            if pid in all_process_map:
                proc = all_process_map[pid]
                self.selected_pids[pid]['cpu_str'] = f"{proc['cpu']:.1f}%"
                self.selected_pids[pid]['mem_str'] = self.format_memory(proc['memory'])
                # Store GPU usage for selection panel
                gpu_info = gpu_processes.get(pid, {})
                self.selected_pids[pid]['gpu_usage'] = gpu_info.get('gpu_usage', 0.0)
        
        # Track processes that currently have GPU usage or are detected as GPU processes
        # (e.g., Intel processes with DRM file descriptors open, even with 0% usage)
        current_gpu_pids = set()
        for pid, gpu_info in gpu_processes.items():
            # Add all processes in gpu_processes (they're detected as GPU processes)
            current_gpu_pids.add(pid)
            # Add to "ever used GPU" set
            self._gpu_used_pids.add(pid)
        
        # Clean up ended processes from "ever used GPU" set
        self._gpu_used_pids = {pid for pid in self._gpu_used_pids if pid in all_pids}
        
        # Combine process info with GPU info
        # Only show processes that have GPU usage (current or historical)
        combined_processes = []
        
        # Add processes that currently have GPU usage or have ever used GPU
        for pid, proc_info in all_process_map.items():
            if pid in current_gpu_pids or pid in self._gpu_used_pids:
                gpu_info = gpu_processes.get(pid, {})
                combined_processes.append({
                    'pid': pid,
                    'name': proc_info['name'],
                    'cpu': proc_info['cpu'],
                    'memory': proc_info['memory'],
                    'started': proc_info.get('started', ''),
                    'started_ts': proc_info.get('started_ts', proc_info.get('started', '')),
                    'gpu_info': gpu_info
                })
        
        # Also include processes that have GPU usage but might not be in regular process list
        for pid, gpu_info in gpu_processes.items():
            if pid not in all_process_map and (pid in current_gpu_pids or pid in self._gpu_used_pids):
                # Try to get basic process info
                try:
                    proc_details = self.process_manager.get_process_details(pid)
                    name = 'Unknown'
                    if proc_details.get('cmdline'):
                        cmdline_parts = proc_details['cmdline'].split()
                        if cmdline_parts:
                            name = cmdline_parts[0].split('/')[-1]  # Get basename
                    combined_processes.append({
                        'pid': pid,
                        'name': name,
                        'cpu': 0.0,
                        'memory': 0,
                        'started': '',
                        'started_ts': '',
                        'gpu_info': gpu_info
                    })
                except Exception:
                    pass
        
        # Filter by search text
        if search_text:
            # When searching, hide already selected items from results
            combined_processes = [
                p for p in combined_processes
                if (search_text in p['name'].lower() or search_text in str(p['pid']))
                and p['pid'] not in self.selected_pids
            ]
        else:
            # Get PIDs of combined processes
            combined_pids = {p['pid'] for p in combined_processes}
            
            # Add selected processes that are not in the list but still exist
            for pid in self.selected_pids:
                if pid not in combined_pids and pid in all_pids:
                    proc = all_process_map[pid]
                    gpu_info = gpu_processes.get(pid, {})
                    combined_processes.append({
                        'pid': pid,
                        'name': proc['name'],
                        'cpu': proc['cpu'],
                        'memory': proc['memory'],
                        'started': proc.get('started', ''),
                        'started_ts': proc.get('started_ts', proc.get('started', '')),
                        'gpu_info': gpu_info
                    })
        
        # Save scroll position as ratio before updating
        vadj = self.gpu_scrolled.get_vadjustment()
        scroll_value = vadj.get_value()
        old_upper = vadj.get_upper()
        old_page_size = vadj.get_page_size()
        # Calculate scroll ratio (0.0 = top, 1.0 = bottom)
        old_max_scroll = old_upper - old_page_size
        scroll_ratio = scroll_value / old_max_scroll if old_max_scroll > 0 else 0.0
        
        # Double buffering: Create new model, populate it, then swap
        self._updating_selection = True
        
        # Save current sort state before swapping model
        sort_column_id, sort_order = self.gpu_list_store.get_sort_column_id()
        
        # Calculate total columns needed
        total_cols = 5 + len(self.gpu_column_mapping) * 3
        col_types = [str] * total_cols
        col_types[3] = int  # PID is int
        new_store = Gtk.ListStore(*col_types)
        
        # Attach sort function for Started column
        new_store.set_sort_func(4, self.sort_gpu_started, None)
        
        for proc in combined_processes:
            row_data = [
                proc['name'],
                f"{proc['cpu']:.1f}%",
                self.format_memory(proc['memory']),
                proc['pid'],
                proc.get('started_ts', proc.get('started', ''))
            ]
            
            # Add GPU columns based on available GPUs
            gpu_info = proc.get('gpu_info', {})
            gpu_type = gpu_info.get('gpu_type', '')
            
            if 'nvidia' in self.gpu_stats.gpu_types:
                if gpu_type == 'nvidia' and (gpu_info.get('gpu_usage', 0) > 0 or 
                                             gpu_info.get('encoding', 0) > 0 or 
                                             gpu_info.get('decoding', 0) > 0):
                    row_data.append(f"{gpu_info.get('gpu_usage', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('encoding', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('decoding', 0):.1f}%")
                else:
                    row_data.extend(["", "", ""])
            
            if 'intel' in self.gpu_stats.gpu_types:
                if gpu_type == 'intel':
                    row_data.append(f"{gpu_info.get('gpu_usage', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('encoding', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('decoding', 0):.1f}%")
                else:
                    row_data.extend(["", "", ""])
            
            if 'amd' in self.gpu_stats.gpu_types:
                if gpu_type == 'amd' and (gpu_info.get('gpu_usage', 0) > 0 or 
                                          gpu_info.get('encoding', 0) > 0 or 
                                          gpu_info.get('decoding', 0) > 0):
                    row_data.append(f"{gpu_info.get('gpu_usage', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('encoding', 0):.1f}%")
                    row_data.append(f"{gpu_info.get('decoding', 0):.1f}%")
                else:
                    row_data.extend(["", "", ""])
            
            new_store.append(row_data)
        
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
        self.gpu_list_store = new_store
        self.gpu_tree_view.set_model(self.gpu_list_store)
        
        # Restore sort state after model swap
        if sort_column_id is not None and sort_column_id >= 0:
            self.gpu_list_store.set_sort_column_id(sort_column_id, sort_order)
        
        # Connect sort change handler to new store
        self.gpu_list_store.connect("sort-column-changed", self.on_gpu_sort_column_changed)
        
        # Restore selection by PID from persistent selection
        selection = self.gpu_tree_view.get_selection()
        if self.selected_pids:
            for i, row in enumerate(self.gpu_list_store):
                if row[3] in self.selected_pids:  # PID column is 3 in GPU list
                    selection.select_path(Gtk.TreePath.new_from_indices([i]))
        
        self._updating_selection = False
        
        # Update the selection panel
        self.update_selection_panel()
    
    def _on_gpu_data_updated(self):
        """Callback from GPU background thread when data is updated.
        
        Uses GLib.idle_add to safely update UI from background thread.
        """
        GLib.idle_add(self._refresh_gpu_ui)
    
    def _refresh_gpu_ui(self):
        """Refresh GPU UI elements (called from GLib.idle_add).
        
        This is called when background GPU data update completes.
        Only refreshes if we're still on the GPU tab.
        """
        if self.current_tab != 'gpu':
            return False  # Don't repeat
        
        # Update GPU process list and stats
        self.refresh_gpu_processes()
        self.update_system_stats()
        
        return False  # Don't repeat (one-shot idle callback)

