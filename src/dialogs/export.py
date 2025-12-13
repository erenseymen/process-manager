# SPDX-License-Identifier: GPL-3.0-or-later
# Export dialog for exporting process list

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw


class ExportDialog(Adw.Window):
    """Dialog for exporting process list."""
    
    def __init__(self, parent, process_manager, tree_view, list_store, selected_pids):
        """
        Args:
            parent: Parent window
            process_manager: ProcessManager instance
            tree_view: The process tree view
            list_store: The list store
            selected_pids: Dict of selected PIDs
        """
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Export Process List",
            default_width=500,
            default_height=400,
        )
        
        self.parent = parent
        self.process_manager = process_manager
        self.tree_view = tree_view
        self.list_store = list_store
        self.selected_pids = selected_pids
        
        self.build_ui()
    
    def build_ui(self):
        """Build the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        main_box.append(content_box)
        
        # Format selection
        format_group = Adw.PreferencesGroup()
        format_group.set_title("Export Format")
        content_box.append(format_group)
        
        self.format_combo = Gtk.ComboBoxText()
        self.format_combo.append("csv", "CSV")
        self.format_combo.append("json", "JSON")
        self.format_combo.append("txt", "Plain Text")
        self.format_combo.set_active_id("csv")
        
        format_row = Adw.ActionRow()
        format_row.set_title("Format")
        format_row.add_suffix(self.format_combo)
        format_group.add(format_row)
        
        # Scope selection
        scope_group = Adw.PreferencesGroup()
        scope_group.set_title("Export Scope")
        content_box.append(scope_group)
        
        self.scope_combo = Gtk.ComboBoxText()
        self.scope_combo.append("all", "All Visible Processes")
        self.scope_combo.append("selected", "Selected Processes Only")
        self.scope_combo.set_active_id("all")
        
        scope_row = Adw.ActionRow()
        scope_row.set_title("Scope")
        scope_row.add_suffix(self.scope_combo)
        scope_group.add(scope_row)
        
        # Column selection
        columns_group = Adw.PreferencesGroup()
        columns_group.set_title("Columns")
        content_box.append(columns_group)
        
        # Get column names
        self.column_names = ["Process Name", "CPU %", "Memory", "Started", "User", "Nice", "PID"]
        self.column_checkboxes = {}
        
        for col_name in self.column_names:
            check = Gtk.CheckButton(label=col_name)
            check.set_active(True)
            self.column_checkboxes[col_name] = check
            columns_group.add(check)
        
        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        content_box.append(button_box)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        button_box.append(cancel_btn)
        
        export_btn = Gtk.Button(label="Export...")
        export_btn.add_css_class("suggested-action")
        export_btn.connect("clicked", self.on_export)
        button_box.append(export_btn)
    
    def on_export(self, button):
        """Handle export button click."""
        # Get selected format
        format_id = self.format_combo.get_active_id()
        
        # Get selected columns
        selected_columns = [name for name, check in self.column_checkboxes.items() if check.get_active()]
        if not selected_columns:
            self.parent.show_error("Please select at least one column")
            return
        
        # Get scope
        scope = self.scope_combo.get_active_id()
        
        # Get data
        if scope == "selected" and self.selected_pids:
            processes = []
            all_processes = self.process_manager.get_processes(show_all=True, my_processes=False, active_only=False, show_kernel_threads=True)
            for proc in all_processes:
                if proc['pid'] in self.selected_pids:
                    processes.append(proc)
        else:
            # Get all visible processes from list store
            processes = []
            for row in self.list_store:
                pid = row[6]  # PID column
                all_processes = self.process_manager.get_processes(show_all=True, my_processes=False, active_only=False, show_kernel_threads=True)
                for proc in all_processes:
                    if proc['pid'] == pid:
                        processes.append(proc)
                        break
        
        if not processes:
            self.parent.show_error("No processes to export")
            return
        
        # Create file chooser
        dialog = Gtk.FileChooserNative(
            title="Save Export File",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Save",
            cancel_label="Cancel"
        )
        
        # Set default filename
        ext = format_id
        dialog.set_current_name(f"processes.{ext}")
        
        # Add filters
        if format_id == "csv":
            filter_csv = Gtk.FileFilter()
            filter_csv.set_name("CSV files")
            filter_csv.add_pattern("*.csv")
            dialog.add_filter(filter_csv)
        elif format_id == "json":
            filter_json = Gtk.FileFilter()
            filter_json.set_name("JSON files")
            filter_json.add_pattern("*.json")
            dialog.add_filter(filter_json)
        else:
            filter_txt = Gtk.FileFilter()
            filter_txt.set_name("Text files")
            filter_txt.add_pattern("*.txt")
            dialog.add_filter(filter_txt)
        
        dialog.connect("response", lambda d, response: self.on_file_selected(d, response, format_id, selected_columns, processes))
        dialog.show()
    
    def on_file_selected(self, dialog, response, format_id, selected_columns, processes):
        """Handle file selection."""
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return
        
        file_path = dialog.get_file().get_path()
        dialog.destroy()
        
        try:
            # Export based on format
            if format_id == "csv":
                self.export_csv(file_path, selected_columns, processes)
            elif format_id == "json":
                self.export_json(file_path, selected_columns, processes)
            else:
                self.export_txt(file_path, selected_columns, processes)
            
            self.parent.show_error(f"Exported {len(processes)} processes to {file_path}")
            self.close()
        except Exception as e:
            self.parent.show_error(f"Export failed: {e}")
    
    def export_csv(self, file_path, columns, processes):
        """Export to CSV format."""
        import csv
        
        # Map column names to process keys
        col_map = {
            "Process Name": "name",
            "CPU %": "cpu",
            "Memory": "memory",
            "Started": "started",
            "User": "user",
            "Nice": "nice",
            "PID": "pid"
        }
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            
            for proc in processes:
                row = []
                for col in columns:
                    key = col_map.get(col, col.lower())
                    if key == "cpu":
                        row.append(f"{proc.get(key, 0):.1f}%")
                    elif key == "memory":
                        # Format memory
                        mem = proc.get(key, 0)
                        if mem >= 1024**3:
                            row.append(f"{mem / (1024**3):.2f} GB")
                        elif mem >= 1024**2:
                            row.append(f"{mem / (1024**2):.2f} MB")
                        elif mem >= 1024:
                            row.append(f"{mem / 1024:.2f} KB")
                        else:
                            row.append(f"{mem} B")
                    else:
                        row.append(str(proc.get(key, "")))
                writer.writerow(row)
    
    def export_json(self, file_path, columns, processes):
        """Export to JSON format."""
        import json
        
        col_map = {
            "Process Name": "name",
            "CPU %": "cpu",
            "Memory": "memory",
            "Started": "started",
            "User": "user",
            "Nice": "nice",
            "PID": "pid"
        }
        
        data = []
        for proc in processes:
            item = {}
            for col in columns:
                key = col_map.get(col, col.lower())
                item[col] = proc.get(key, "")
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def export_txt(self, file_path, columns, processes):
        """Export to plain text format."""
        col_map = {
            "Process Name": "name",
            "CPU %": "cpu",
            "Memory": "memory",
            "Started": "started",
            "User": "user",
            "Nice": "nice",
            "PID": "pid"
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            # Header
            f.write("\t".join(columns) + "\n")
            f.write("-" * (len("\t".join(columns))) + "\n")
            
            # Data
            for proc in processes:
                row = []
                for col in columns:
                    key = col_map.get(col, col.lower())
                    if key == "cpu":
                        row.append(f"{proc.get(key, 0):.1f}%")
                    elif key == "memory":
                        mem = proc.get(key, 0)
                        if mem >= 1024**3:
                            row.append(f"{mem / (1024**3):.2f} GB")
                        elif mem >= 1024**2:
                            row.append(f"{mem / (1024**2):.2f} MB")
                        elif mem >= 1024:
                            row.append(f"{mem / 1024:.2f} KB")
                        else:
                            row.append(f"{mem} B")
                    else:
                        row.append(str(proc.get(key, "")))
                f.write("\t".join(row) + "\n")
