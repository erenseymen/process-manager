# SPDX-License-Identifier: GPL-3.0-or-later
# Process Manager

"""Process Manager - A modern GTK4-based system process manager for Linux.

This package provides a graphical interface for monitoring and managing
system processes, including CPU/memory usage tracking, process termination,
and system resource monitoring.
"""

from .constants import APP_ID, APP_NAME, APP_VERSION

__all__ = ['APP_ID', 'APP_NAME', 'APP_VERSION']
__version__ = APP_VERSION
