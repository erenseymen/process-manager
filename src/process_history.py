# SPDX-License-Identifier: GPL-3.0-or-later
# Process history and logging

"""Process lifecycle tracking and resource usage history."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Set

from gi.repository import GLib

if TYPE_CHECKING:
    pass


class ProcessHistory:
    """Tracks process lifecycle events and resource usage over time."""
    
    def __init__(self, max_history_days: int = 7) -> None:
        """Initialize ProcessHistory.
        
        Args:
            max_history_days: Maximum number of days to keep history (default: 7).
        """
        self.max_history_days = max_history_days
        self._config_dir = Path(GLib.get_user_config_dir()) / "process-manager"
        self._history_file = self._config_dir / "process_history.json"
        
        # In-memory tracking
        self._known_pids: Set[int] = set()  # PIDs we've seen
        self._process_starts: Dict[int, float] = {}  # PID -> start timestamp
        self._process_stats_history: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self._process_lifetime_stats: Dict[int, Dict[str, Any]] = {}
        
        # Load existing history
        self.load_history()
    
    def update_processes(self, processes: List[Dict[str, Any]]) -> None:
        """Update process history with current process list.
        
        Args:
            processes: List of current processes (from ProcessManager.get_processes()).
        """
        current_time = time.time()
        current_pids = {p['pid'] for p in processes}
        
        # Detect new processes
        new_pids = current_pids - self._known_pids
        for pid in new_pids:
            self._process_starts[pid] = current_time
            self._known_pids.add(pid)
        
        # Record current stats for all processes
        for proc in processes:
            pid = proc['pid']
            stats_entry = {
                'timestamp': current_time,
                'cpu': proc.get('cpu', 0.0),
                'memory': proc.get('memory', 0),
                'state': proc.get('state', 'R'),
                'nice': proc.get('nice', 0),
            }
            self._process_stats_history[pid].append(stats_entry)
            
            # Update lifetime stats
            if pid not in self._process_lifetime_stats:
                self._process_lifetime_stats[pid] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'max_cpu': 0.0,
                    'max_memory': 0,
                    'total_samples': 0,
                }
            
            lifetime = self._process_lifetime_stats[pid]
            lifetime['last_seen'] = current_time
            lifetime['max_cpu'] = max(lifetime['max_cpu'], proc.get('cpu', 0.0))
            lifetime['max_memory'] = max(lifetime['max_memory'], proc.get('memory', 0))
            lifetime['total_samples'] += 1
        
        # Detect exited processes
        exited_pids = self._known_pids - current_pids
        for pid in exited_pids:
            if pid in self._process_starts:
                start_time = self._process_starts[pid]
                end_time = current_time
                lifetime = end_time - start_time
                
                # Store exit event
                if pid not in self._process_lifetime_stats:
                    self._process_lifetime_stats[pid] = {
                        'first_seen': start_time,
                        'last_seen': end_time,
                        'max_cpu': 0.0,
                        'max_memory': 0,
                        'total_samples': 0,
                    }
                
                self._process_lifetime_stats[pid]['last_seen'] = end_time
                self._process_lifetime_stats[pid]['lifetime_seconds'] = lifetime
                
                # Remove from active tracking
                self._known_pids.discard(pid)
                self._process_starts.pop(pid, None)
        
        # Clean old history
        cutoff_time = current_time - (self.max_history_days * 24 * 3600)
        for pid in list(self._process_stats_history.keys()):
            self._process_stats_history[pid] = [
                entry for entry in self._process_stats_history[pid]
                if entry['timestamp'] >= cutoff_time
            ]
            if not self._process_stats_history[pid]:
                del self._process_stats_history[pid]
        
        # Clean old lifetime stats for processes not seen in a while
        for pid in list(self._process_lifetime_stats.keys()):
            if pid not in self._known_pids and self._process_lifetime_stats[pid]['last_seen'] < cutoff_time:
                del self._process_lifetime_stats[pid]
    
    def get_process_lifetime_stats(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get lifetime statistics for a process.
        
        Args:
            pid: Process ID.
            
        Returns:
            Dictionary with lifetime stats or None if process not in history:
            - first_seen: Timestamp when first seen
            - last_seen: Timestamp when last seen
            - lifetime_seconds: Total lifetime (if exited)
            - max_cpu: Maximum CPU usage seen
            - max_memory: Maximum memory usage seen
            - total_samples: Number of samples collected
        """
        if pid in self._process_lifetime_stats:
            stats = self._process_lifetime_stats[pid].copy()
            # Convert timestamps to datetime strings for display
            stats['first_seen_datetime'] = datetime.fromtimestamp(stats['first_seen']).isoformat()
            stats['last_seen_datetime'] = datetime.fromtimestamp(stats['last_seen']).isoformat()
            if 'lifetime_seconds' in stats:
                stats['lifetime_formatted'] = self._format_duration(stats['lifetime_seconds'])
            return stats
        return None
    
    def get_process_history(self, pid: int, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical data for a process.
        
        Args:
            pid: Process ID.
            hours: Number of hours of history to return.
            
        Returns:
            List of historical entries, each with timestamp, cpu, memory, etc.
        """
        if pid not in self._process_stats_history:
            return []
        
        cutoff_time = time.time() - (hours * 3600)
        return [
            entry for entry in self._process_stats_history[pid]
            if entry['timestamp'] >= cutoff_time
        ]
    
    def get_all_process_lifetime_stats(self) -> Dict[int, Dict[str, Any]]:
        """Get lifetime statistics for all tracked processes.
        
        Returns:
            Dictionary mapping PID to lifetime stats.
        """
        result = {}
        for pid, stats in self._process_lifetime_stats.items():
            stats_copy = stats.copy()
            stats_copy['first_seen_datetime'] = datetime.fromtimestamp(stats['first_seen']).isoformat()
            stats_copy['last_seen_datetime'] = datetime.fromtimestamp(stats['last_seen']).isoformat()
            if 'lifetime_seconds' in stats:
                stats_copy['lifetime_formatted'] = self._format_duration(stats['lifetime_seconds'])
            result[pid] = stats_copy
        return result
    
    def export_history(self, output_file: Path, format: str = 'json', pids: Optional[List[int]] = None) -> bool:
        """Export process history to a file.
        
        Args:
            output_file: Path to output file.
            format: Export format ('json' or 'csv').
            pids: Optional list of PIDs to export. If None, exports all.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            if format == 'json':
                export_data = {}
                if pids:
                    for pid in pids:
                        if pid in self._process_lifetime_stats:
                            export_data[pid] = self.get_process_lifetime_stats(pid)
                        if pid in self._process_stats_history:
                            export_data[f'{pid}_history'] = self.get_process_history(pid)
                else:
                    export_data['lifetime_stats'] = self.get_all_process_lifetime_stats()
                    export_data['history'] = dict(self._process_stats_history)
                
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            
            elif format == 'csv':
                import csv
                with open(output_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['PID', 'First Seen', 'Last Seen', 'Lifetime', 'Max CPU %', 'Max Memory', 'Samples'])
                    
                    stats_to_export = self._process_lifetime_stats
                    if pids:
                        stats_to_export = {pid: self._process_lifetime_stats[pid] for pid in pids if pid in self._process_lifetime_stats}
                    
                    for pid, stats in stats_to_export.items():
                        lifetime = stats.get('lifetime_seconds', time.time() - stats['first_seen'])
                        writer.writerow([
                            pid,
                            datetime.fromtimestamp(stats['first_seen']).isoformat(),
                            datetime.fromtimestamp(stats['last_seen']).isoformat(),
                            self._format_duration(lifetime),
                            f"{stats['max_cpu']:.2f}",
                            stats['max_memory'],
                            stats['total_samples']
                        ])
            
            return True
        except (OSError, IOError, ValueError) as e:
            print(f"Error exporting history: {e}")
            return False
    
    def load_history(self) -> None:
        """Load history from disk."""
        try:
            if self._history_file.exists():
                with open(self._history_file, 'r') as f:
                    data = json.load(f)
                    
                    # Restore lifetime stats (convert datetime strings back to timestamps)
                    if 'lifetime_stats' in data:
                        for pid_str, stats in data['lifetime_stats'].items():
                            pid = int(pid_str)
                            stats['first_seen'] = datetime.fromisoformat(stats.get('first_seen_datetime', '')).timestamp()
                            stats['last_seen'] = datetime.fromisoformat(stats.get('last_seen_datetime', '')).timestamp()
                            self._process_lifetime_stats[pid] = stats
                    
                    # Restore known PIDs
                    self._known_pids = set(self._process_lifetime_stats.keys())
        except (OSError, IOError, json.JSONDecodeError, ValueError, KeyError):
            # If loading fails, start fresh
            pass
    
    def save_history(self) -> None:
        """Save history to disk."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for saving
            data = {
                'lifetime_stats': {}
            }
            
            for pid, stats in self._process_lifetime_stats.items():
                stats_copy = stats.copy()
                stats_copy['first_seen_datetime'] = datetime.fromtimestamp(stats['first_seen']).isoformat()
                stats_copy['last_seen_datetime'] = datetime.fromtimestamp(stats['last_seen']).isoformat()
                data['lifetime_stats'][str(pid)] = stats_copy
            
            with open(self._history_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except (OSError, IOError) as e:
            print(f"Error saving history: {e}")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds.
            
        Returns:
            Formatted string like "5d 3h 42m 30s".
        """
        if seconds < 0:
            return "0s"
        
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return ' '.join(parts)

