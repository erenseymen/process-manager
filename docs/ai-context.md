# AI Context

This file contains important context about the codebase for AI assistants.

---

<!-- Add new context entries below this line -->

## Implementation Patterns (2025-12-12)

### UI Component Architecture
- **Selection Panel** (`ProcessManagerWindow.create_selection_panel()`): Processes grouped by name in ListBox with relative usage bars (color-coded thresholds: low=green/blue, medium=orange/yellow, high=red), sorted by memory descending
- **System Stats Bar** (`ProcessManagerWindow.create_stats_bar()`): Bottom bar with Memory/Swap/Disk sections using circular progress indicators, updated via `update_system_stats()` periodic timer
- **Tab System**: Uses `Adw.ViewStack` with `SLIDE` transition; tab changes trigger `on_tab_changed()` callback; `ViewSwitcher` in header for visual navigation
- **Tabs**: Processes, GPU, and Ports tabs; each tab has its own view and refresh logic

### GPU Monitoring Implementation (2025-12-12, performance update)
- Detection in `GPUStats._detect_gpus()` runs at initialization (checks for nvidia-smi, intel_gpu_top, radeontop)
- Lazy execution: GPU commands only execute when GPU tab is visible (performance optimization via `on_tab_changed()`)
- Process list columns dynamically added when GPU tab active: GPU usage, encoding usage, decoding usage (per GPU type)
- GPU stats bar updates conditionally based on active tab
- **Background Threading**: GPU data collected in background thread (`start_background_updates()`) to avoid UI blocking
- **Parallel Execution**: Multiple GPU types (NVIDIA, Intel, AMD) queried in parallel using `ThreadPoolExecutor`
- **Cache TTL**: 1.8 seconds (aligned with 2s refresh interval)
- DRM file descriptor scanning removed for performance (intel_gpu_top provides sufficient process detection)

### Intel GPU Per-Process Stats (2025-12-12)
- Uses `sudo -n intel_gpu_top -J -o -` with timeout for Intel GPU process monitoring
- JSON output is an array of readings; parser extracts last complete object
- Client info structure: `clients -> {client_id} -> {name, pid, engine-classes}`
- Engine classes use hyphen: `engine-classes -> Render/3D|Video -> busy` (string values)
- `_parse_intel_gpu_top_json()` helper handles incomplete JSON arrays (from timeout kill)
- `run_host_command()` supports timeout parameter for long-running commands
- Video engine (`Video`) usage mapped to both encoding and decoding columns

### GPU Tab Async Updates
- `GPUStats.start_background_updates(callback)`: Starts daemon thread for continuous GPU data collection
- `GPUStats.stop_background_updates()`: Stops background thread (called on tab switch away or window close)
- `_on_gpu_data_updated()`: Callback using `GLib.idle_add()` for thread-safe UI updates
- Background thread updates shared cache; UI reads from cache without blocking

### Process Details Dialog (2025-12-12)
- `ProcessDetailsDialog` class shows all process information in a modal window
- Opened by pressing Enter on a selected process in Processes or GPU tab
- Displays: PID, Name, User, State, CPU, Memory, Nice, Started, Command Line, Executable, Working Directory, Threads, File Descriptors, Environment Variables
- All fields are copyable: single-line fields have copy button, multi-line fields use selectable text views
- Uses `Adw.PreferencesGroup` for organized layout with sections
- Escape key closes the dialog

### Ports Tab Implementation (2025-12-12)
- `PortStats` class in `port_stats.py` collects open ports using `ss -tunap` command
- Parses ss output to extract: PID, process name, protocol (tcp/udp/tcp6/udp6), local/remote addresses and ports, connection state
- Ports view displays: Process Name, PID, Protocol, Local Address, Local Port, Remote Address, Remote Port, State
- Right-click context menu: Show Process Details, End Process
- Enter key on selected port shows process details dialog
- Search/filter works on process name, PID, port number, protocol, and address
- Refresh happens on tab switch and via auto-refresh timer

### Design Patterns
- Type hints used throughout for improved IDE support
- Settings stored in JSON format at `~/.config/process-manager/settings.json`
- Module separation: high-level operations in `process_manager.py`, low-level system commands in `ps_commands.py`

### Phase 2 Features (2025-12-12)

#### Process Tree View
- Toggle button in header to switch between list and tree view modes
- Tree view shows parent-child relationships using PPID data from `ps_commands.py`
- Uses `Gtk.TreeStore` for hierarchical data, `Gtk.ListStore` for flat view
- Tree structure built in `_build_process_tree()` method, recursively populated via `_populate_tree_store()`
- Selection restoration works for both tree and list modes via `_restore_tree_selection()`
- Setting: `tree_view_mode` (boolean) persists user preference

#### Process Renice/Priority UI
- Right-click context menu option "Change Priority..." opens `ReniceDialog`
- Dialog allows setting nice value from -20 (highest) to 19 (lowest)
- Supports batch renice for multiple selected processes
- Shows current priority and process name(s) in dialog
- Error handling for permission denied and process not found cases
- Toast notifications for success/failure

#### Export Functionality
- File → Export menu option opens `ExportDialog`
- Export formats: CSV, JSON, Plain Text
- Column selection with checkboxes for all process columns
- Export scope: All Visible Processes or Selected Processes Only
- File chooser dialog with format-specific filters
- Proper formatting of memory values and CPU percentages in exports

#### Advanced Search/Filter
- Advanced filter button next to search bar opens `AdvancedFilterDialog`
- Filter criteria: CPU range (%), Memory range (%), Username (regex), Process State
- Regex support in search entry (automatic detection, falls back to simple search on invalid regex)
- Search applies to process name, PID, and username
- Filter presets infrastructure in place (settings key: `filter_presets`)

