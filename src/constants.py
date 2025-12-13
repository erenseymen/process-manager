# SPDX-License-Identifier: GPL-3.0-or-later
# Application constants

"""Application-wide constants and configuration values."""

# Application identifier
APP_ID = "io.github.processmanager.ProcessManager"

# Application metadata
APP_NAME = "Process Manager"
APP_VERSION = "1.0.0"
APP_WEBSITE = "https://github.com/processmanager/processmanager"
APP_ISSUE_URL = "https://github.com/processmanager/processmanager/issues"

# Default refresh interval in milliseconds
DEFAULT_REFRESH_INTERVAL = 2000

# CSS styles for the application
APP_CSS = """
.high-usage-panel {
    background-color: alpha(@warning_color, 0.1);
}

.high-usage-chip {
    padding: 4px 10px;
    border-radius: 16px;
    background-color: alpha(@warning_color, 0.15);
    border: 1px solid alpha(@warning_color, 0.3);
}

.high-usage-chip.change-up {
    background-color: alpha(@error_color, 0.15);
    border-color: alpha(@error_color, 0.3);
}

.high-usage-chip.change-down {
    background-color: alpha(@success_color, 0.15);
    border-color: alpha(@success_color, 0.3);
}

.high-usage-chip .chip-name {
    font-weight: bold;
}

.high-usage-chip .chip-value {
    font-size: 0.9em;
    opacity: 0.85;
}

.selection-chip {
    padding: 4px 10px;
    border-radius: 16px;
    background-color: alpha(@accent_bg_color, 0.15);
    border: 1px solid alpha(@accent_color, 0.3);
}

.selection-chip .chip-name {
    font-weight: bold;
}

.selection-chip .chip-stats {
    font-size: 0.9em;
    opacity: 0.7;
}

.selection-chip .chip-remove {
    min-width: 20px;
    min-height: 20px;
    padding: 0;
}

.keycap {
    padding: 4px 8px;
    border-radius: 4px;
    background-color: alpha(@window_bg_color, 0.5);
    border: 1px solid alpha(@borders, 0.5);
    font-size: 0.9em;
    font-weight: 500;
}
"""

