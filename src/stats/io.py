# SPDX-License-Identifier: GPL-3.0-or-later
# I/O statistics

"""Utilities for retrieving process I/O statistics (disk and network I/O)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple

if TYPE_CHECKING:
    pass


def get_host_proc_path() -> Path:
    """Get the path to host /proc.
    
    Returns:
        Path to /proc (or /run/host/proc in Flatpak).
    """
    if os.path.exists('/run/host/proc') and os.path.isdir('/run/host/proc'):
        return Path('/run/host/proc')
    return Path('/proc')


class IOStats:
    """I/O statistics monitoring for processes (disk and network I/O)."""
    
    def __init__(self) -> None:
        """Initialize IOStats."""
        self._proc_path = get_host_proc_path()
        self._prev_io_stats: Dict[int, Dict[str, int]] = {}  # PID -> {read_bytes, write_bytes, etc.}
    
    def get_process_io(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get I/O statistics for a specific process.
        
        Args:
            pid: Process ID to get I/O stats for.
            
        Returns:
            Dictionary with I/O statistics or None if unavailable:
            - read_bytes: Bytes read from disk (int)
            - write_bytes: Bytes written to disk (int)
            - read_chars: Characters read from terminal (int)
            - write_chars: Characters written to terminal (int)
            - read_bytes_per_sec: Read rate (bytes/sec) (float)
            - write_bytes_per_sec: Write rate (bytes/sec) (float)
        """
        try:
            io_file = self._proc_path / str(pid) / 'io'
            if not io_file.exists():
                return None
            
            io_data: Dict[str, int] = {}
            with open(io_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        try:
                            io_data[key] = int(value)
                        except ValueError:
                            continue
            
            # Calculate rates
            current_time = time.time()
            read_bytes_per_sec = 0.0
            write_bytes_per_sec = 0.0
            
            if pid in self._prev_io_stats:
                prev = self._prev_io_stats[pid]
                time_diff = max(current_time - prev.get('_time', current_time), 0.001)
                read_diff = io_data.get('read_bytes', 0) - prev.get('read_bytes', 0)
                write_diff = io_data.get('write_bytes', 0) - prev.get('write_bytes', 0)
                read_bytes_per_sec = read_diff / time_diff
                write_bytes_per_sec = write_diff / time_diff
            
            # Store current stats with timestamp
            io_data['_time'] = current_time
            self._prev_io_stats[pid] = io_data.copy()
            
            return {
                'read_bytes': io_data.get('read_bytes', 0),
                'write_bytes': io_data.get('write_bytes', 0),
                'read_chars': io_data.get('rchar', 0),
                'write_chars': io_data.get('wchar', 0),
                'read_bytes_per_sec': read_bytes_per_sec,
                'write_bytes_per_sec': write_bytes_per_sec,
                'read_syscalls': io_data.get('syscr', 0),
                'write_syscalls': io_data.get('syscw', 0),
            }
        except (OSError, IOError, PermissionError, ValueError):
            return None
    
    def get_all_processes_io(self, pids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get I/O statistics for multiple processes.
        
        Args:
            pids: List of process IDs to get I/O stats for.
            
        Returns:
            Dictionary mapping PID to I/O statistics dict (same format as get_process_io).
        """
        result: Dict[int, Dict[str, Any]] = {}
        for pid in pids:
            io_data = self.get_process_io(pid)
            if io_data:
                result[pid] = io_data
        return result
    
    def clear_cache(self) -> None:
        """Clear cached I/O statistics."""
        self._prev_io_stats.clear()
    
    def get_network_io_by_pid(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get network I/O statistics for a process using /proc/net/sockstat.
        
        Note: Linux doesn't provide per-process network I/O stats directly.
        This is a placeholder for future implementation using netlink or other methods.
        
        Args:
            pid: Process ID.
            
        Returns:
            Dictionary with network I/O stats or None.
            Currently returns None as per-process network I/O requires additional work.
        """
        # Per-process network I/O is not easily available via /proc
        # Would need to parse /proc/net/tcp, /proc/net/udp and correlate with
        # process file descriptors, or use netlink sockets
        # For now, return None to indicate unavailable
        return None

