# SPDX-License-Identifier: GPL-3.0-or-later
# Process management functions

import os
import signal
import pwd
import subprocess
from datetime import datetime
from pathlib import Path


def is_flatpak():
    """Check if running inside a Flatpak sandbox."""
    return os.path.exists('/.flatpak-info')


def get_host_proc_path():
    """Get the path to host /proc.
    
    When running in Flatpak, we need to access the host's /proc
    through /run/host/proc if available, otherwise fall back to /proc.
    """
    # Try /run/host/proc first (available with --filesystem=host)
    if os.path.exists('/run/host/proc') and os.path.isdir('/run/host/proc'):
        return Path('/run/host/proc')
    return Path('/proc')


class ProcessManager:
    """Manages process information and operations."""
    
    def __init__(self):
        self._cpu_times = {}  # Cache for CPU time calculations
        self._last_update = 0
        self._proc_path = get_host_proc_path()
        self._is_flatpak = is_flatpak()
    
    def get_processes(self, show_all=True, my_processes=False, active_only=False):
        """Get list of all processes with their information."""
        processes = []
        current_uid = os.getuid()
        
        # Get system stats for CPU calculation
        total_cpu_time = self._get_total_cpu_time()
        
        for pid_dir in self._proc_path.iterdir():
            if not pid_dir.name.isdigit():
                continue
            
            try:
                pid = int(pid_dir.name)
                proc_info = self._get_process_info(pid, total_cpu_time)
                
                if proc_info is None:
                    continue
                
                # Apply filters
                if my_processes and proc_info['uid'] != current_uid:
                    continue
                
                if active_only and proc_info['cpu'] < 0.1:
                    continue
                
                processes.append(proc_info)
                
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                continue
        
        return processes
    
    def _get_process_info(self, pid, total_cpu_time):
        """Get information for a single process."""
        proc_path = self._proc_path / str(pid)
        
        try:
            # Read process stat
            stat_path = proc_path / 'stat'
            with open(stat_path, 'r') as f:
                stat_line = f.read()
            
            # Parse stat - handle process names with parentheses
            # Format: pid (comm) state ppid ...
            first_paren = stat_line.index('(')
            last_paren = stat_line.rindex(')')
            name = stat_line[first_paren + 1:last_paren]
            stat_parts = stat_line[last_paren + 2:].split()
            
            # Get various fields from stat
            # Fields after (comm): state, ppid, pgrp, session, tty_nr, tpgid, flags,
            # minflt, cminflt, majflt, cmajflt, utime, stime, cutime, cstime, priority, nice
            state = stat_parts[0]
            utime = int(stat_parts[11])
            stime = int(stat_parts[12])
            nice = int(stat_parts[16])
            starttime = int(stat_parts[19])
            
            # Calculate CPU usage
            cpu_percent = self._calculate_cpu_percent(pid, utime, stime, total_cpu_time)
            
            # Get memory usage from statm
            statm_path = proc_path / 'statm'
            with open(statm_path, 'r') as f:
                statm_parts = f.read().split()
            
            # RSS is the second field, in pages
            page_size = os.sysconf('SC_PAGESIZE')
            rss_pages = int(statm_parts[1])
            memory_bytes = rss_pages * page_size
            
            # Get user info from status
            status_path = proc_path / 'status'
            uid = None
            with open(status_path, 'r') as f:
                for line in f:
                    if line.startswith('Uid:'):
                        uid = int(line.split()[1])
                        break
            
            # Get username
            try:
                username = pwd.getpwuid(uid).pw_name if uid is not None else "unknown"
            except KeyError:
                username = str(uid) if uid is not None else "unknown"
            
            # Calculate start time
            boot_time = self._get_boot_time()
            clock_ticks = os.sysconf('SC_CLK_TCK')
            start_timestamp = boot_time + (starttime / clock_ticks)
            start_datetime = datetime.fromtimestamp(start_timestamp)
            
            # Format start time based on how long ago
            now = datetime.now()
            if start_datetime.date() == now.date():
                started_str = start_datetime.strftime("%H:%M:%S")
            elif (now - start_datetime).days < 7:
                started_str = start_datetime.strftime("%a %H:%M")
            else:
                started_str = start_datetime.strftime("%Y-%m-%d")
            
            return {
                'pid': pid,
                'name': name,
                'cpu': cpu_percent,
                'memory': memory_bytes,
                'started': started_str,
                'user': username,
                'nice': nice,
                'uid': uid,
                'state': state
            }
            
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, IndexError):
            return None
    
    def _get_total_cpu_time(self):
        """Get total CPU time from /proc/stat."""
        try:
            with open(self._proc_path / 'stat', 'r') as f:
                cpu_line = f.readline()
            
            parts = cpu_line.split()
            # cpu user nice system idle iowait irq softirq steal guest guest_nice
            total = sum(int(p) for p in parts[1:])
            return total
        except:
            return 1  # Avoid division by zero
    
    def _calculate_cpu_percent(self, pid, utime, stime, total_cpu_time):
        """Calculate CPU percentage for a process."""
        current_time = utime + stime
        
        if pid in self._cpu_times:
            prev_time, prev_total = self._cpu_times[pid]
            time_delta = current_time - prev_time
            total_delta = total_cpu_time - prev_total
            
            if total_delta > 0:
                cpu_percent = (time_delta / total_delta) * 100 * os.cpu_count()
            else:
                cpu_percent = 0.0
        else:
            cpu_percent = 0.0
        
        # Update cache
        self._cpu_times[pid] = (current_time, total_cpu_time)
        
        return max(0.0, min(cpu_percent, 100.0 * os.cpu_count()))
    
    def _get_boot_time(self):
        """Get system boot time."""
        try:
            with open(self._proc_path / 'stat', 'r') as f:
                for line in f:
                    if line.startswith('btime'):
                        return int(line.split()[1])
        except:
            pass
        return 0
    
    def kill_process(self, pid, signal_num=signal.SIGTERM):
        """Send a signal to a process."""
        os.kill(pid, signal_num)
    
    def renice_process(self, pid, nice_value):
        """Change the nice value of a process."""
        os.setpriority(os.PRIO_PROCESS, pid, nice_value)
    
    def get_process_details(self, pid):
        """Get detailed information about a process."""
        proc_path = self._proc_path / str(pid)
        
        details = {}
        
        try:
            # Command line
            cmdline_path = proc_path / 'cmdline'
            with open(cmdline_path, 'r') as f:
                cmdline = f.read().replace('\x00', ' ').strip()
            details['cmdline'] = cmdline or '[kernel thread]'
            
            # Working directory
            try:
                cwd = os.readlink(proc_path / 'cwd')
                details['cwd'] = cwd
            except:
                details['cwd'] = 'N/A'
            
            # Executable path
            try:
                exe = os.readlink(proc_path / 'exe')
                details['exe'] = exe
            except:
                details['exe'] = 'N/A'
            
            # Environment (limited)
            try:
                environ_path = proc_path / 'environ'
                with open(environ_path, 'r') as f:
                    environ = f.read().replace('\x00', '\n')
                details['environ'] = environ[:2000]  # Limit size
            except:
                details['environ'] = 'N/A'
            
            # File descriptors count
            try:
                fd_count = len(list((proc_path / 'fd').iterdir()))
                details['fd_count'] = fd_count
            except:
                details['fd_count'] = 0
            
            # Threads count
            try:
                thread_count = len(list((proc_path / 'task').iterdir()))
                details['threads'] = thread_count
            except:
                details['threads'] = 1
            
        except (FileNotFoundError, PermissionError):
            pass
        
        return details

