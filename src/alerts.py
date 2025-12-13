# SPDX-License-Identifier: GPL-3.0-or-later
# Process alerts and notifications

"""Alert system for monitoring process resource usage thresholds."""

from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Set, Callable, Tuple
from gi.repository import GLib, Gio

if TYPE_CHECKING:
    pass

# Application ID for notifications
APP_ID = "io.github.processmanager.ProcessManager"


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
        # Track alerts by (pid, rule_id) -> last_alert_time to avoid spamming
        self._alerted_cache: Dict[Tuple[int, str], float] = {}
        self._alert_cooldown = 60.0  # Don't re-alert for same pid+rule within 60 seconds
    
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
        
        current_time = time.time()
        show_notifications = self.settings.get("alert_notifications", True)
        play_sound = self.settings.get("alert_sound", False)
        
        for proc in processes:
            pid = proc['pid']
            cpu = proc.get('cpu', 0.0)
            memory_bytes = proc.get('memory', 0)
            memory_percent = (memory_bytes / mem_total * 100) if mem_total > 0 else 0
            
            for rule in rules:
                rule_id = rule.get('id', '')
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
                    
                    # Check cooldown - don't spam notifications for the same alert
                    last_alert_time = self._alerted_cache.get(alert_key, 0)
                    should_notify = (current_time - last_alert_time) >= self._alert_cooldown
                    
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
                    
                    # Send desktop notification if enabled and not in cooldown
                    if should_notify and show_notifications:
                        title = f"Process Alert: {proc.get('name', 'Unknown')}"
                        self.send_notification(title, message, play_sound)
                        self._alerted_cache[alert_key] = current_time
                    
                    # Trigger callback if provided
                    if self.on_alert_callback:
                        self.on_alert_callback(pid, rule, proc)
        
        # Clean up old entries from cache (older than 5 minutes)
        cutoff = current_time - 300
        self._alerted_cache = {
            k: v for k, v in self._alerted_cache.items()
            if v >= cutoff
        }
        
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
        
        Uses Gio.Notification when running as a proper GApplication,
        falls back to notify-send command otherwise.
        
        Args:
            title: Notification title.
            body: Notification body text.
            sound: Whether to play a sound.
        """
        try:
            # Try to get the running application
            app = Gio.Application.get_default()
            
            if app is not None:
                # Use Gio.Notification (preferred for GNOME apps)
                notification = Gio.Notification.new(title)
                notification.set_body(body)
                notification.set_priority(Gio.NotificationPriority.HIGH)
                
                # Set icon
                notification.set_icon(Gio.ThemedIcon.new("dialog-warning-symbolic"))
                
                # Generate a unique notification ID based on content
                notification_id = f"alert-{hash(title + body) % 10000}"
                app.send_notification(notification_id, notification)
            else:
                # Fallback to notify-send command
                self._send_notification_via_command(title, body, sound)
                
        except Exception as e:
            # If Gio.Notification fails, try notify-send as fallback
            try:
                self._send_notification_via_command(title, body, sound)
            except Exception:
                pass  # Silently fail if notifications aren't available
    
    def _send_notification_via_command(self, title: str, body: str, sound: bool = False) -> None:
        """Send notification using notify-send command.
        
        Args:
            title: Notification title.
            body: Notification body text.
            sound: Whether to play a sound (not supported via notify-send).
        """
        try:
            cmd = [
                'notify-send',
                '--app-name', 'Process Manager',
                '--icon', 'dialog-warning-symbolic',
                '--urgency', 'critical',
                title,
                body
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except (FileNotFoundError, OSError):
            pass  # notify-send not available

