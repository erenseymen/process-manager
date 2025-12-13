# SPDX-License-Identifier: GPL-3.0-or-later
# UI mixin classes for Process Manager

from .stats_bar import StatsBarMixin
from .selection_panel import SelectionPanelMixin
from .bookmarks_panel import BookmarksPanelMixin
from .high_usage_panel import HighUsagePanelMixin

__all__ = [
    'StatsBarMixin',
    'SelectionPanelMixin',
    'BookmarksPanelMixin',
    'HighUsagePanelMixin',
]
