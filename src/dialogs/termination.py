# SPDX-License-Identifier: GPL-3.0-or-later
# Process termination dialog with status tracking

import signal

from ..ps_commands import is_process_running_via_host

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gdk


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
        
        # Group processes by name
        self.process_groups = {}
        for p in processes:
            name = p['name']
            pid = p['pid']
            if name not in self.process_groups:
                self.process_groups[name] = []
            self.process_groups[name].append(pid)
        
        # Keep individual process tracking for status
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
        
        # Build process rows (grouped by name)
        self.process_rows = {}
        for name, pids in sorted(self.process_groups.items()):
            row = self.create_process_row(name, pids)
            self.process_rows[name] = row
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
    
    def create_process_row(self, name, pids):
        """Create a row for a process group in the list."""
        row = Adw.ActionRow()
        
        # Set title with count if multiple processes
        if len(pids) == 1:
            row.set_title(name)
            row.set_subtitle(f"PID: {pids[0]}")
        else:
            row.set_title(f"{name} ({len(pids)})")
            pids_str = ", ".join(str(pid) for pid in sorted(pids)[:5])
            if len(pids) > 5:
                pids_str += f", ... (+{len(pids) - 5} more)"
            row.set_subtitle(f"PIDs: {pids_str}")
        
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
        kill_button.connect("clicked", lambda b: self.on_kill_group(name, pids))
        kill_button.set_visible(False)
        row.add_suffix(kill_button)
        
        return {
            'row': row,
            'status_icon': status_icon,
            'kill_button': kill_button,
            'pids': pids
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
    
    def update_process_row(self, name):
        """Update the visual state of a process group row."""
        if name not in self.process_rows:
            return
        
        row_data = self.process_rows[name]
        pids = row_data['pids']
        
        # Check status of all PIDs in this group
        statuses = [self.processes[pid]['status'] for pid in pids if pid in self.processes]
        
        # Determine overall status
        if all(s == 'terminated' for s in statuses):
            # All terminated
            row_data['status_icon'].set_from_icon_name("emblem-ok-symbolic")
            row_data['status_icon'].add_css_class("success")
            row_data['kill_button'].set_visible(False)
            if len(pids) == 1:
                row_data['row'].set_subtitle(f"PID: {pids[0]} - Terminated")
            else:
                row_data['row'].set_subtitle(f"{len(pids)} processes - All terminated")
        elif any(s == 'running' for s in statuses):
            # Some still running
            row_data['status_icon'].set_from_icon_name("dialog-warning-symbolic")
            row_data['status_icon'].add_css_class("warning")
            row_data['kill_button'].set_visible(True)
            running_count = sum(1 for s in statuses if s == 'running')
            terminated_count = sum(1 for s in statuses if s == 'terminated')
            if len(pids) == 1:
                row_data['row'].set_subtitle(f"PID: {pids[0]} - Still running")
            else:
                row_data['row'].set_subtitle(f"{running_count} running, {terminated_count} terminated")
        else:
            # All pending
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
                all_terminated = False
                any_running = True
            else:
                self.processes[pid]['status'] = 'terminated'
        
        # Update all process group rows
        for name in self.process_rows:
            self.update_process_row(name)
        
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
        return is_process_running_via_host(pid)
    
    def on_kill_group(self, name, pids):
        """Handle kill button for a process group."""
        for pid in pids:
            if pid in self.processes and self.processes[pid]['status'] == 'running':
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
