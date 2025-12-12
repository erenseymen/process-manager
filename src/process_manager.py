# SPDX-License-Identifier: GPL-3.0-or-later
# Process management functions

"""Process management module providing process listing and control operations."""

from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING, Dict, List, Any

from .ps_commands import (
    get_processes_via_ps,
    get_process_details_via_ps,
    kill_process_via_host,
    renice_process_via_host,
)

if TYPE_CHECKING:
    from signal import Signals


# Signal number to name mapping
_SIGNAL_NAMES: Dict[int, str] = {
    signal.SIGTERM: 'TERM',
    signal.SIGKILL: 'KILL',
    signal.SIGINT: 'INT',
    signal.SIGHUP: 'HUP',
    signal.SIGSTOP: 'STOP',
    signal.SIGCONT: 'CONT',
}


class ProcessManager:
    """Manages process information and operations.
    
    This class provides methods to list processes, send signals to processes,
    change process priority, and get detailed process information.
    """
    
    def get_processes(
        self,
        show_all: bool = True,
        my_processes: bool = False,
        active_only: bool = False,
        show_kernel_threads: bool = False
    ) -> List[Dict[str, Any]]:
        """Get list of all processes with their information.
        
        Args:
            show_all: If True, show all processes (default).
            my_processes: If True, only return processes owned by current user.
            active_only: If True, only return processes with CPU > 0.1%.
            show_kernel_threads: If True, include kernel threads in results.
            
        Returns:
            List of process dictionaries with keys:
            pid, name, cpu, memory, started, user, nice, uid, state
        """
        current_uid = os.getuid()
        return get_processes_via_ps(current_uid, my_processes, active_only, show_kernel_threads)
    
    def kill_process(self, pid: int, signal_num: int = signal.SIGTERM) -> None:
        """Send a signal to a process.
        
        Args:
            pid: The process ID to signal.
            signal_num: The signal to send (default: SIGTERM).
            
        Raises:
            ProcessLookupError: If the signal could not be sent.
        """
        signal_name = _SIGNAL_NAMES.get(signal_num, str(signal_num))
        kill_process_via_host(pid, signal_name)
    
    def renice_process(self, pid: int, nice_value: int) -> None:
        """Change the nice value of a process.
        
        Args:
            pid: The process ID to renice.
            nice_value: The new nice value (-20 to 19).
            
        Raises:
            PermissionError: If permission is denied.
            ProcessLookupError: If the process doesn't exist.
        """
        renice_process_via_host(pid, nice_value)
    
    def get_process_details(self, pid: int) -> Dict[str, Any]:
        """Get detailed information about a process.
        
        Args:
            pid: The process ID to get details for.
            
        Returns:
            Dictionary with process details: cmdline, cwd, exe, environ, fd_count, threads
        """
        return get_process_details_via_ps(pid)
