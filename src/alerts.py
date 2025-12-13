# SPDX-License-Identifier: GPL-3.0-or-later
# Process alerts and notifications

"""Alert system for monitoring process resource usage thresholds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Any, Set, Callable
from gi.repository import GLib, Gio

if TYPE_CHECKING:
    pass


class ProcessAlerts:
    """Monitor processes and trigger alerts when thresholds are exceeded."""
    
    def __init__(self, settings, on_alert_callback: Optional[Callable] = None) -> None:
        """Initialize ProcessAlerts.
        
        Args:
            settings: Settings instance.
            on_alert_callback: Optional callback function(pid, rule, process_info) called when alert triggers.
        """
        self.settings = settings
        self.on_alert_callback = on_alert_callback
        self._alerted_pids: Set[int] = set()  # PIDs that have already triggered alerts
        self._notification_app = Gio.Application.get_default()
    
    def check_processes(self, processes: List[Dict[str, Any]], mem_total: int) -> List[Dict[str, Any]]:
        """Check processes against alert rules and trigger alerts.
        
        Args:
            processes: List of process dictionaries.
            mem_total: Total system memory in bytes (for percentage calculations).
            
        Returns:
            List of triggered alerts (dicts with pid, rule, message).
        """
        if not self.settings.get("alerts_enabled", False):
            return []
        
        triggered_alerts = []
        rules = self.settings.get("alert_rules", [])
        
        if not rules:
            return []
        
        for proc in processes:
            pid = proc['pid']
            cpu = proc.get('cpu', 0.0)
            memory_bytes = proc.get('memory', 0)
            memory_percent = (memory_bytes / mem_total * 100) if mem_total > 0 else 0
            
            for rule in rules:
                rule_id = rule.get('id')
                rule_type = rule.get('type')  # 'cpu' or 'memory'
                threshold = rule.get('threshold', 0)
                enabled = rule.get('enabled', True)
                
                if not enabled:
                    continue
                
                # Check threshold
                triggered = False
                if rule_type == 'cpu' and cpu >= threshold:
                    triggered = True
                elif rule_type == 'memory' and memory_percent >= threshold:
                    triggered = True
                
                if triggered:
                    # Create alert key to avoid duplicate alerts
                    alert_key = (pid, rule_id)
                    
                    # Only trigger if we haven't alerted for this pid+rule combination recently
                    # For simplicity, we'll reset _alerted_pids on each refresh cycle
                    # (alerts will retrigger if threshold still exceeded)
                    
                    message = self._format_alert_message(rule, proc, cpu, memory_percent)
                    
                    alert = {
                        'pid': pid,
                        'rule': rule,
                        'message': message,
                        'cpu': cpu,
                        'memory_percent': memory_percent,
                        'process_name': proc.get('name', 'Unknown')
                    }
                    
                    triggered_alerts.append(alert)
                    
                    # Trigger notification if callback provided
                    if self.on_alert_callback:
                        self.on_alert_callback(pid, rule, proc)
        
        # Reset alerted PIDs for next check cycle
        self._alerted_pids.clear()
        
        return triggered_alerts
    
    def _format_alert_message(self, rule: Dict[str, Any], proc: Dict[str, Any], 
                             cpu: float, memory_percent: float) -> str:
        """Format alert message.
        
        Args:
            rule: Alert rule dictionary.
            proc: Process dictionary.
            cpu: CPU usage percentage.
            memory_percent: Memory usage percentage.
            
        Returns:
            Formatted alert message string.
        """
        rule_type = rule.get('type', 'cpu')
        threshold = rule.get('threshold', 0)
        process_name = proc.get('name', 'Unknown')
        pid = proc.get('pid', 0)
        
        if rule_type == 'cpu':
            return f"Process '{process_name}' (PID {pid}) CPU usage is {cpu:.1f}% (threshold: {threshold}%)"
        else:
            return f"Process '{process_name}' (PID {pid}) Memory usage is {memory_percent:.1f}% (threshold: {threshold}%)"
    
    def send_notification(self, title: str, body: str, sound: bool = False) -> None:
        """Send a desktop notification.
        
        Args:
            title: Notification title.
            body: Notification body text.
            sound: Whether to play a sound.
        """
        # Use GLib.Notification for desktop notifications
        # This is a simple implementation - could be enhanced with actions, urgency, etc.
        try:
            # Note: Gtk.Application.get_default() needs to have notification support
            # For now, we'll use a simpler approach via notify-send command or GLib
            pass  # Placeholder - notification implementation depends on platform
        except Exception:
            pass

