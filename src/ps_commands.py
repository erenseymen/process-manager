# SPDX-License-Identifier: GPL-3.0-or-later
# PS command utilities for process information retrieval

import os
import subprocess


def is_flatpak():
    """Check if running inside a Flatpak sandbox."""
    return os.path.exists('/.flatpak-info')


def run_host_command(cmd):
    """Run a command on the host system using flatpak-spawn.
    
    When running in Flatpak, uses flatpak-spawn --host to execute
    commands on the host system. Otherwise, runs the command directly.
    
    Args:
        cmd: List of command arguments to execute.
        
    Returns:
        The stdout output of the command as a string.
    """
    if is_flatpak():
        full_cmd = ['flatpak-spawn', '--host'] + cmd
    else:
        full_cmd = cmd
    
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return result.stdout


def get_processes_via_ps(current_uid, my_processes, active_only, show_kernel_threads, is_kernel_thread_func):
    """Get processes using ps command via flatpak-spawn --host.
    
    This function is primarily used when running in a Flatpak sandbox,
    where direct /proc access may be limited.
    
    Args:
        current_uid: The current user's UID for filtering.
        my_processes: If True, only return processes owned by current user.
        active_only: If True, only return processes with CPU > 0.1%.
        show_kernel_threads: If True, include kernel threads in results.
        is_kernel_thread_func: Callback function to check if a process is a kernel thread.
        
    Returns:
        List of process dictionaries with keys:
        pid, name, cpu, memory, started, user, nice, uid, state
    """
    processes = []
    
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
                
                # Filter kernel threads (PPID 2 is kthreadd, or check if executable doesn't exist)
                if not show_kernel_threads:
                    if is_kernel_thread_func(pid, ppid):
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
                    'state': state
                })
                
            except (ValueError, IndexError):
                continue
                
    except Exception:
        pass
    
    return processes


def kill_process_via_host(pid, signal_name):
    """Send a signal to a process on the host system.
    
    Uses flatpak-spawn --host to send signals to host processes
    since os.kill() only works within the sandbox.
    
    Args:
        pid: The process ID to signal.
        signal_name: The signal name (e.g., 'TERM', 'KILL', 'INT').
        
    Raises:
        ProcessLookupError: If the signal could not be sent.
    """
    cmd = ['kill', f'-{signal_name}', str(pid)]
    result = subprocess.run(
        ['flatpak-spawn', '--host'] + cmd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"Failed to send {signal_name} to process {pid}"
        raise ProcessLookupError(error_msg)

