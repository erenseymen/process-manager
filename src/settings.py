# SPDX-License-Identifier: GPL-3.0-or-later
# Settings management

import json
import os
from pathlib import Path
from gi.repository import GLib


class Settings:
    """Application settings manager."""
    
    DEFAULTS = {
        "refresh_interval": 2000,  # milliseconds
        "show_all_processes": True,
        "show_kernel_threads": False,
        "confirm_kill": True,
        "cpu_threshold_warning": 80,
        "memory_threshold_warning": 80,
        "sort_column": "cpu",
        "sort_descending": True,
        "visible_columns": ["name", "cpu", "memory", "started", "user", "nice", "pid"],
        "theme": "system",  # system, light, dark
        "window_width": 900,
        "window_height": 600,
    }
    
    def __init__(self):
        self._settings = dict(self.DEFAULTS)
        self._config_dir = Path(GLib.get_user_config_dir()) / "process-manager"
        self._config_file = self._config_dir / "settings.json"
        self.load()
    
    def load(self):
        """Load settings from file."""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r') as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load settings: {e}")
    
    def save(self):
        """Save settings to file."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save settings: {e}")
    
    def get(self, key, default=None):
        """Get a setting value."""
        return self._settings.get(key, default if default is not None else self.DEFAULTS.get(key))
    
    def set(self, key, value):
        """Set a setting value."""
        self._settings[key] = value
        self.save()
    
    def reset(self):
        """Reset all settings to defaults."""
        self._settings = dict(self.DEFAULTS)
        self.save()

