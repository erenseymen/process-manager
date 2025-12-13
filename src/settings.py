# SPDX-License-Identifier: GPL-3.0-or-later
# Settings management

"""Settings management module for persisting application preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from gi.repository import GLib


SettingValue = Union[int, float, bool, str, list]


class Settings:
    """Application settings manager.
    
    Handles loading, saving, and managing application settings.
    Settings are stored in JSON format in the user's config directory.
    """
    
    DEFAULTS: Dict[str, SettingValue] = {
        "refresh_interval": 2000,  # milliseconds
        "show_kernel_threads": False,
        "confirm_kill": True,
        "cpu_threshold_warning": 80,
        "memory_threshold_warning": 80,
        "cpu_change_threshold": 10,  # Show processes with CPU change >= this %
        "memory_change_threshold": 5,  # Show processes with memory change >= this %
        "sort_column": "cpu",
        "sort_descending": True,
        "theme": "system",  # system, light, dark
        "window_width": 900,
        "window_height": 600,
        "show_all_toggle": True,  # All/User toggle state (True = All, False = User)
        "auto_refresh": True,  # Auto refresh toggle state
        "tree_view_mode": False,  # Process tree view mode
        "filter_presets": [],  # Saved filter presets
        # Column visibility and layout
        "column_visibility": {},  # Dict mapping column name to visible (bool)
        "column_order": [],  # List of column names in display order
        "custom_columns": [],  # List of custom column definitions
        # Process history
        "history_enabled": True,  # Enable process history tracking
        "history_max_days": 7,  # Maximum days to keep history
        # Alerts
        "alerts_enabled": False,  # Enable process alerts
        "alert_rules": [],  # List of alert rule dicts
        "alert_notifications": True,  # Show desktop notifications
        "alert_sound": False,  # Play sound on alerts
        # Bookmarks
        "bookmarked_pids": [],  # List of bookmarked process PIDs
    }
    
    def __init__(self) -> None:
        self._settings: Dict[str, SettingValue] = dict(self.DEFAULTS)
        self._config_dir = Path(GLib.get_user_config_dir()) / "process-manager"
        self._config_file = self._config_dir / "settings.json"
        self.load()
    
    def load(self) -> None:
        """Load settings from file.
        
        If the settings file doesn't exist or is invalid, defaults are used.
        """
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load settings: {e}")
    
    def save(self) -> None:
        """Save settings to file.
        
        Creates the config directory if it doesn't exist.
        """
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save settings: {e}")
    
    def get(self, key: str, default: Optional[SettingValue] = None) -> SettingValue:
        """Get a setting value.
        
        Args:
            key: The setting key to retrieve.
            default: Default value if key is not found (falls back to DEFAULTS).
            
        Returns:
            The setting value.
        """
        if default is not None:
            return self._settings.get(key, default)
        return self._settings.get(key, self.DEFAULTS.get(key))
    
    def set(self, key: str, value: SettingValue) -> None:
        """Set a setting value and save to disk.
        
        Args:
            key: The setting key to set.
            value: The value to store.
        """
        self._settings[key] = value
        self.save()
    
    def reset(self) -> None:
        """Reset all settings to defaults and save to disk."""
        self._settings = dict(self.DEFAULTS)
        self.save()

