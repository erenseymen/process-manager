# SPDX-License-Identifier: GPL-3.0-or-later
# PS command utilities for process information retrieval

"""Utilities for retrieving process information via ps and other system commands."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List


def is_flatpak() -> bool:
    """Check if running inside a Flatpak sandbox.
    
    Returns:
        True if running inside Flatpak, False otherwise.
    """
    return os.path.exists('/.flatpak-info')


def run_host_command(cmd: List[str], timeout: int = 5) -> str:
    """Run a command on the host system using flatpak-spawn.
    
    When running in Flatpak, uses flatpak-spawn --host to execute
    commands on the host system. Otherwise, runs the command directly.
    
    Args:
        cmd: List of command arguments to execute.
        timeout: Maximum time in seconds to wait for the command (default: 5).
        
    Returns:
        The stdout output of the command as a string.
    """
    if is_flatpak():
        full_cmd = ['flatpak-spawn', '--host'] + cmd
    else:
        full_cmd = cmd
    
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except subprocess.TimeoutExpired:
        return ""


def get_processes_via_ps(
    current_uid: int,
    my_processes: bool,
    active_only: bool,
    show_kernel_threads: bool
) -> List[Dict[str, Any]]:
    """Get processes using ps command.
    
    Args:
        current_uid: The current user's UID for filtering.
        my_processes: If True, only return processes owned by current user.
        active_only: If True, only return processes with CPU > 0.1%.
        show_kernel_threads: If True, include kernel threads in results.
        
    Returns:
        List of process dictionaries with keys:
        pid, name, cpu, memory, started, user, nice, uid, state
    """
    processes: List[Dict[str, Any]] = []
    my_pid = os.getpid()
    
    try:
        # Use ps with custom format to get all needed info
        # pid, comm, %cpu, rss (in KB), lstart, user, nice, uid, state, ppid
        cmd = ['ps', '-eo', 'pid,comm,%cpu,rss,lstart,user,nice,uid,state,ppid', '--no-headers']
        output = run_host_command(cmd)
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            
            try:
                # Parse ps output - lstart has spaces so we need careful parsing
                # Format: PID COMMAND %CPU RSS DAY MON DD HH:MM:SS YYYY USER NI UID STATE PPID
                parts = line.split()
                if len(parts) < 14:
                    continue
                
                pid = int(parts[0])
                name = parts[1]
                cpu = float(parts[2])
                memory_kb = int(parts[3])
                memory_bytes = memory_kb * 1024
                
                # lstart is 5 fields: Day Mon DD HH:MM:SS YYYY
                started_str = parts[7]  # Just use time part HH:MM:SS
                
                # Rest of fields after lstart
                user = parts[9]
                nice = int(parts[10])
                uid = int(parts[11])
                state = parts[12]
                ppid = int(parts[13])
                
                # Filter out our own ps command (spawned by this process)
                if name == 'ps' and ppid == my_pid:
                    continue
                
                # Filter kernel threads (PPID 2 is kthreadd)
                if not show_kernel_threads:
                    if ppid == 2 or pid == 2:
                        continue
                
                # Apply filters
                if my_processes and uid != current_uid:
                    continue
                
                if active_only and cpu < 0.1:
                    continue
                
                processes.append({
                    'pid': pid,
                    'name': name,
                    'cpu': cpu,
                    'memory': memory_bytes,
                    'started': started_str,
                    'user': user,
                    'nice': nice,
                    'uid': uid,
                    'state': state,
                    'ppid': ppid
                })
                
            except (ValueError, IndexError):
                continue
                
    except (OSError, subprocess.SubprocessError):
        pass
    
    return processes


def get_process_details_via_ps(pid: int) -> Dict[str, Any]:
    """Get detailed information about a process using ps and other commands.
    
    Args:
        pid: The process ID to get details for.
        
    Returns:
        Dictionary with process details: cmdline, cwd, exe, environ, fd_count, threads
    """
    details: Dict[str, Any] = {}
    
    try:
        # Get command line using ps
        cmd = ['ps', '-p', str(pid), '-o', 'args=']
        output = run_host_command(cmd).strip()
        details['cmdline'] = output if output else '[kernel thread]'
    except (OSError, subprocess.SubprocessError):
        details['cmdline'] = 'N/A'
    
    try:
        # Get working directory using pwdx
        cmd = ['pwdx', str(pid)]
        output = run_host_command(cmd).strip()
        # Output format: "pid: /path/to/cwd"
        if ':' in output:
            details['cwd'] = output.split(':', 1)[1].strip()
        else:
            details['cwd'] = 'N/A'
    except (OSError, subprocess.SubprocessError):
        details['cwd'] = 'N/A'
    
    try:
        # Get executable path using readlink
        cmd = ['readlink', '-f', f'/proc/{pid}/exe']
        output = run_host_command(cmd).strip()
        details['exe'] = output if output else 'N/A'
    except (OSError, subprocess.SubprocessError):
        details['exe'] = 'N/A'
    
    try:
        # Get environment variables using cat
        cmd = ['cat', f'/proc/{pid}/environ']
        output = run_host_command(cmd)
        if output:
            environ = output.replace('\x00', '\n')
            details['environ'] = environ[:2000] if environ else 'N/A'
        else:
            details['environ'] = 'N/A (permission denied or process not accessible)'
    except (OSError, subprocess.SubprocessError) as e:
        # Check if it's a permission error
        error_str = str(e).lower()
        if 'permission denied' in error_str or 'access denied' in error_str:
            details['environ'] = 'N/A (permission denied - run with appropriate privileges)'
        else:
            details['environ'] = f'N/A (error: {str(e)})'
    
    try:
        # Get file descriptor count using ls
        cmd = ['ls', '-1', f'/proc/{pid}/fd']
        output = run_host_command(cmd)
        fd_count = len(output.strip().split('\n')) if output.strip() else 0
        details['fd_count'] = fd_count
    except (OSError, subprocess.SubprocessError):
        details['fd_count'] = 0
    
    try:
        # Get thread count using ps
        cmd = ['ps', '-p', str(pid), '-o', 'nlwp=']
        output = run_host_command(cmd).strip()
        details['threads'] = int(output) if output else 1
    except (OSError, subprocess.SubprocessError, ValueError):
        details['threads'] = 1
    
    return details


def kill_process_via_host(pid: int, signal_name: str) -> None:
    """Send a signal to a process on the host system.
    
    Uses flatpak-spawn --host to send signals to host processes
    when running in Flatpak sandbox.
    
    Args:
        pid: The process ID to signal.
        signal_name: The signal name (e.g., 'TERM', 'KILL', 'INT').
        
    Raises:
        ProcessLookupError: If the signal could not be sent.
    """
    cmd = ['kill', f'-{signal_name}', str(pid)]
    
    if is_flatpak():
        full_cmd = ['flatpak-spawn', '--host'] + cmd
    else:
        full_cmd = cmd
    
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"Failed to send {signal_name} to process {pid}"
        raise ProcessLookupError(error_msg)


def renice_process_via_host(pid: int, nice_value: int) -> None:
    """Change the nice value of a process.
    
    Args:
        pid: The process ID to renice.
        nice_value: The new nice value (-20 to 19).
        
    Raises:
        PermissionError: If permission is denied.
        ProcessLookupError: If the process doesn't exist.
    """
    cmd = ['renice', str(nice_value), '-p', str(pid)]
    
    if is_flatpak():
        full_cmd = ['flatpak-spawn', '--host'] + cmd
    else:
        full_cmd = cmd
    
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"Failed to renice process {pid}"
        if 'Permission denied' in error_msg or 'permission denied' in error_msg.lower():
            raise PermissionError(error_msg)
        raise ProcessLookupError(error_msg)
