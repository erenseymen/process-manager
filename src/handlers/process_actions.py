# SPDX-License-Identifier: GPL-3.0-or-later
# Process actions mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import signal
from gi.repository import Gtk, Adw, GLib

from ..dialogs import TerminationDialog, ShortcutsWindow


class ProcessActionsMixin:
    """Mixin class providing process action functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - selected_pids: dict
    - settings: Settings instance
    - process_manager: ProcessManager instance
    - toast_overlay: Adw.ToastOverlay
    - _get_current_tree_view_info: method
    - _refresh_current_tab: method
    """
    
    def terminate_selected_processes(self):
        """Terminate selected processes using SIGTERM.
        
        Terminates processes directly without confirmation. If any processes
        fail to terminate after a delay, shows a dialog with force kill option.
        """
        if not self.selected_pids:
            return
        
        processes = []
        for pid, info in self.selected_pids.items():
            processes.append({'pid': pid, 'name': info.get('name', 'Unknown')})
        
        # Send SIGTERM to all selected processes immediately
        for pid in list(self.selected_pids.keys()):
            try:
                self.process_manager.kill_process(pid)
            except Exception as e:
                self.show_error(f"Failed to terminate process {pid}: {e}")
        
        # After a short delay, check if any processes are still running
        # and show dialog only for those that failed to terminate
        def check_and_show_dialog():
            from ..ps_commands import is_process_running_via_host
            
            still_running = []
            for process in processes:
                pid = process['pid']
                if is_process_running_via_host(pid):
                    still_running.append(process)
                else:
                    # Process terminated successfully, remove from selection
                    if pid in self.selected_pids:
                        del self.selected_pids[pid]
            
            if still_running:
                # Show dialog only for processes that failed to terminate
                dialog = TerminationDialog(
                    self, self.process_manager, still_running, skip_confirmation=True
                )
                dialog.present()
            else:
                # All processes terminated, just refresh
                self._refresh_current_tab()
            
            return False  # Don't repeat
        
        # Wait 500ms for processes to terminate, then check
        GLib.timeout_add(500, check_and_show_dialog)
    
    def force_kill_selected_processes(self):
        """Force kill selected processes using SIGKILL."""
        if not self.selected_pids:
            return
        
        for pid in list(self.selected_pids.keys()):
            try:
                self.process_manager.kill_process(pid, signal.SIGKILL)
                # Remove from persistent selection
                if pid in self.selected_pids:
                    del self.selected_pids[pid]
            except Exception as e:
                self.show_error(f"Failed to kill process {pid}: {e}")
        
        # Refresh after killing
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
        
        # Send SIGTERM to all processes directly (no confirmation)
        self.kill_processes_direct(processes)
    
    def show_termination_dialog(self, processes):
        """Show termination dialog with status tracking."""
        dialog = TerminationDialog(self, self.process_manager, processes)
        dialog.present()
    
    def show_shortcuts(self):
        """Show keyboard shortcuts window."""
        shortcuts_window = ShortcutsWindow(self)
        shortcuts_window.present()
    
    def kill_processes_direct(self, processes):
        """Kill the specified processes directly without confirmation.
        
        Sends SIGTERM and after a delay checks if processes terminated.
        If any are still running, shows a dialog with force kill option.
        
        Args:
            processes: List of dicts with 'pid' and 'name' keys, OR list of PIDs
        """
        # Handle both old (list of PIDs) and new (list of dicts) format
        if processes and isinstance(processes[0], int):
            processes = [{'pid': pid, 'name': 'Unknown'} for pid in processes]
        
        # Send SIGTERM to all processes
        for process in processes:
            pid = process['pid']
            try:
                self.process_manager.kill_process(pid)
            except Exception as e:
                self.show_error(f"Failed to terminate process {pid}: {e}")
        
        # After a short delay, check if any processes are still running
        def check_and_show_dialog():
            from ..ps_commands import is_process_running_via_host
            
            still_running = []
            for process in processes:
                pid = process['pid']
                if is_process_running_via_host(pid):
                    still_running.append(process)
                else:
                    # Process terminated successfully, remove from selection
                    if pid in self.selected_pids:
                        del self.selected_pids[pid]
            
            if still_running:
                # Show dialog only for processes that failed to terminate
                dialog = TerminationDialog(
                    self, self.process_manager, still_running, skip_confirmation=True
                )
                dialog.present()
            else:
                # All processes terminated, just refresh
                self._refresh_current_tab()
            
            return False  # Don't repeat
        
        # Wait 500ms for processes to terminate, then check
        GLib.timeout_add(500, check_and_show_dialog)
    
    def show_error(self, message):
        """Show error toast."""
        toast = Adw.Toast(title=message, timeout=3)
        self.toast_overlay.add_toast(toast)
    
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
