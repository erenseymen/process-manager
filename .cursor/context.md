# AI Context

This file contains important context about the codebase for AI assistants.

---

<!-- Add new context entries below this line -->

## UI Components (2025-12-12)

### Selection Panel
- Located in `src/window.py` in `ProcessManagerWindow.create_selection_panel()`
- Shows selected processes grouped by name vertically in a ListBox
- Each process group displays:
  - Process name with count (if multiple instances)
  - PID information
  - Memory usage bar (relative to max selected)
  - CPU usage bar (relative to max selected)
- Bars are color-coded: low (green/blue), medium (orange/yellow), high (red)
- Sorted by memory usage descending for easy comparison

### System Stats Bar (2025-12-12)
- Located at the bottom of the window in `ProcessManagerWindow.create_stats_bar()`
- Displays three system resource sections: Memory, Swap, and Disk
- Each section shows:
  - Circular progress indicator (color-coded)
  - Title label
  - Usage details: "used (percentage) of total"
- Memory section also shows cache information
- Stats are updated periodically via `update_system_stats()` method
- Disk usage is retrieved via `SystemStats.get_disk_info()` using `shutil.disk_usage()`

