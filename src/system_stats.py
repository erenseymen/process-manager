# SPDX-License-Identifier: GPL-3.0-or-later
# System statistics

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Union


def get_host_proc_path() -> Path:
    """Get the path to host /proc.
    
    Returns:
        Path to /proc (or /run/host/proc in Flatpak).
    """
    if os.path.exists('/run/host/proc') and os.path.isdir('/run/host/proc'):
        return Path('/run/host/proc')
    return Path('/proc')


class SystemStats:
    """System memory and CPU statistics."""
    
    def __init__(self) -> None:
        self._proc_path = get_host_proc_path()
    
    def get_memory_info(self) -> Dict[str, int]:
        """Get memory and swap information.
        
        Returns:
            Dictionary with memory statistics in bytes.
        """
        meminfo: Dict[str, int] = {}
        default_result = {
            'mem_total': 0,
            'mem_used': 0,
            'mem_free': 0,
            'mem_available': 0,
            'mem_cache': 0,
            'swap_total': 0,
            'swap_used': 0,
            'swap_free': 0
        }
        
        try:
            with open(self._proc_path / 'meminfo', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(':')
                        value = int(parts[1]) * 1024  # Convert from KB to bytes
                        meminfo[key] = value
        except (OSError, IOError, ValueError) as e:
            return default_result
        
        mem_total = meminfo.get('MemTotal', 0)
        mem_free = meminfo.get('MemFree', 0)
        mem_available = meminfo.get('MemAvailable', 0)
        mem_buffers = meminfo.get('Buffers', 0)
        mem_cached = meminfo.get('Cached', 0)
        mem_sreclaimable = meminfo.get('SReclaimable', 0)
        
        # Cache includes buffers, cached, and reclaimable slab
        mem_cache = mem_buffers + mem_cached + mem_sreclaimable
        
        # Used memory (excluding buffers/cache)
        mem_used = mem_total - mem_available
        
        swap_total = meminfo.get('SwapTotal', 0)
        swap_free = meminfo.get('SwapFree', 0)
        swap_used = swap_total - swap_free
        
        return {
            'mem_total': mem_total,
            'mem_used': mem_used,
            'mem_free': mem_free,
            'mem_available': mem_available,
            'mem_cache': mem_cache,
            'swap_total': swap_total,
            'swap_used': swap_used,
            'swap_free': swap_free
        }
    
    def get_cpu_info(self) -> Dict[str, Union[str, int, float]]:
        """Get CPU information.
        
        Returns:
            Dictionary with CPU model, cores, threads, and frequency.
        """
        cpu_info: Dict[str, Union[str, int, float]] = {
            'model': 'Unknown',
            'cores': 0,
            'threads': 0,
            'frequency': 0.0
        }
        
        try:
            with open(self._proc_path / 'cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        cpu_info['model'] = line.split(':')[1].strip()
                    elif line.startswith('cpu cores'):
                        cpu_info['cores'] = int(line.split(':')[1].strip())
                    elif line.startswith('siblings'):
                        cpu_info['threads'] = int(line.split(':')[1].strip())
                    elif line.startswith('cpu MHz'):
                        cpu_info['frequency'] = float(line.split(':')[1].strip())
        except (OSError, IOError, ValueError, IndexError):
            pass
        
        return cpu_info
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds.
        
        Returns:
            System uptime in seconds, or 0 on error.
        """
        try:
            with open(self._proc_path / 'uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                return uptime_seconds
        except (OSError, IOError, ValueError, IndexError):
            return 0.0
    
    def format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format.
        
        Args:
            seconds: Uptime in seconds.
            
        Returns:
            Human-readable uptime string (e.g., "5d 3h 42m").
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        
        return ' '.join(parts)
    
    def get_load_average(self) -> Dict[str, float]:
        """Get system load average.
        
        Returns:
            Dictionary with 1min, 5min, and 15min load averages.
        """
        try:
            with open(self._proc_path / 'loadavg', 'r') as f:
                parts = f.read().split()
                return {
                    '1min': float(parts[0]),
                    '5min': float(parts[1]),
                    '15min': float(parts[2])
                }
        except (OSError, IOError, ValueError, IndexError):
            return {'1min': 0.0, '5min': 0.0, '15min': 0.0}

