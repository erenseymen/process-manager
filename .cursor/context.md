# AI Context

This file contains important context about the codebase for AI assistants.

---

<!-- Add new context entries below this line -->

## Implementation Patterns (2025-12-12)

### UI Component Architecture
- **Selection Panel** (`ProcessManagerWindow.create_selection_panel()`): Processes grouped by name in ListBox with relative usage bars (color-coded thresholds: low=green/blue, medium=orange/yellow, high=red), sorted by memory descending
- **System Stats Bar** (`ProcessManagerWindow.create_stats_bar()`): Bottom bar with Memory/Swap/Disk sections using circular progress indicators, updated via `update_system_stats()` periodic timer
- **Tab System**: Uses `Adw.ViewStack` with `SLIDE` transition; tab changes trigger `on_tab_changed()` callback; `ViewSwitcher` in header for visual navigation

### GPU Monitoring Implementation
- Detection in `GPUStats._detect_gpus()` runs at initialization (checks for nvidia-smi, intel_gpu_top, radeontop)
- Lazy execution: GPU commands only execute when GPU tab is visible (performance optimization via `on_tab_changed()`)
- Process list columns dynamically added when GPU tab active: GPU usage, encoding usage, decoding usage (per GPU type)
- GPU stats bar updates conditionally based on active tab

### Design Patterns
- Type hints used throughout for improved IDE support
- Settings stored in JSON format at `~/.config/process-manager/settings.json`
- Module separation: high-level operations in `process_manager.py`, low-level system commands in `ps_commands.py`

