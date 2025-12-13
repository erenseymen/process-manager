# SPDX-License-Identifier: GPL-3.0-or-later
# Dialog classes for Process Manager

from .process_details import ProcessDetailsDialog
from .renice import ReniceDialog
from .export import ExportDialog
from .shortcuts import ShortcutsWindow
from .termination import TerminationDialog

__all__ = [
    'ProcessDetailsDialog',
    'ReniceDialog',
    'ExportDialog',
    'ShortcutsWindow',
    'TerminationDialog',
]
