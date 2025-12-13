# AI Context

This file contains important context about the codebase for AI assistants.

---

<!-- Add new context entries below this line -->

## Module Structure (2025-12-13)

### Code Organization
The codebase is organized into modular packages for maintainability:

```
src/
├── window.py           # Main ProcessManagerWindow (~2200 lines)
├── dialogs/            # Dialog classes (extracted from window.py)
│   ├── __init__.py     # Re-exports all dialogs
│   ├── process_details.py  # ProcessDetailsDialog
│   ├── renice.py           # ReniceDialog
│   ├── export.py           # ExportDialog
│   ├── shortcuts.py        # ShortcutsWindow
│   └── termination.py      # TerminationDialog
├── tabs/               # Tab mixin classes
│   ├── __init__.py     # Re-exports mixins
│   ├── gpu_tab.py      # GPUTabMixin
│   └── ports_tab.py    # PortsTabMixin
└── [other modules...]
```

### Mixin Pattern for Tabs
- `ProcessManagerWindow` uses multiple inheritance: `GPUTabMixin`, `PortsTabMixin`, `Adw.ApplicationWindow`
- Each mixin provides methods for its respective tab (creation, refresh, event handling)
- Mixins expect certain attributes to exist on `self` (e.g., `settings`, `process_manager`, `selected_pids`)
- This pattern separates tab-specific logic while maintaining a single window class

### Dialog Package
- All dialogs are standalone `Adw.Window` subclasses
- Dialogs receive `parent` and `process_manager` as constructor arguments (no circular imports)
- Import via: `from .dialogs import ProcessDetailsDialog, ReniceDialog, ...`

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

#### Search/Filter
- Simple text search in search entry
- Search applies to process name, PID, and username

### Phase 3 Features (2025-01-XX)

#### I/O Statistics Module
- `IOStats` class in `io_stats.py` collects disk I/O statistics from `/proc/{pid}/io`
- Tracks read/write bytes, characters, syscalls, and calculates per-second rates
- Rates calculated using time.time() timestamps and delta between updates
- Cache-based approach prevents rate spikes from restarted processes

#### Process History/Logging
- `ProcessHistory` class in `process_history.py` tracks process lifecycle and resource usage
- Detects process start/stop events by comparing PID sets between refreshes
- Stores lifetime statistics: first_seen, last_seen, max_cpu, max_memory, total_samples
- History persisted to JSON file in config directory
- Configurable retention period (default: 7 days)
- Export functionality for JSON and CSV formats
- Integrated into refresh_processes() to update on each cycle

#### Alerts System
- `ProcessAlerts` class in `alerts.py` monitors processes against configurable rules
- Alert rules support CPU and memory thresholds
- Rules stored in settings with enabled/disabled state
- Infrastructure for desktop notifications (implementation pending)
- Integrated check in process refresh cycle

#### Custom Columns & Settings
- Extended `Settings` class with new keys:
  - `column_visibility`: Dict mapping column names to visible state
  - `column_order`: List of column names in display order
  - `custom_columns`: List of custom column definitions
  - `history_enabled`: Enable/disable process history tracking
  - `history_max_days`: Maximum days to keep history
  - `alerts_enabled`: Enable/disable alert monitoring
  - `alert_rules`: List of alert rule dictionaries
  - `alert_notifications`: Show desktop notifications
  - `alert_sound`: Play sound on alerts
  - `bookmarked_pids`: List of bookmarked process PIDs

### Phase 4 Features (2025-01-XX)

#### Network Traffic Monitoring
- Enhanced ports tab with traffic statistics per connection
- Tracks bytes sent/received using `ss -i` command
- Calculates per-second rates using cache-based approach (similar to I/O stats)
- Displays columns: Sent, Received, Sent/s, Recv/s
- Traffic data cached to prevent rate spikes from restarted processes
- Columns are sortable and right-aligned for numeric values

#### Process Bookmarks
- Right-click context menu option to bookmark/unbookmark processes
- Bookmarks panel above selection panel showing all bookmarked processes
- Displays CPU and memory usage for each bookmarked process
- Click bookmark to select process in main list
- Unbookmark button in bookmark row
- Bookmarks persist across sessions via settings
- Automatically removes bookmarks for processes that no longer exist

### Phase 5 Features (2025-12-13)

#### Disk I/O Columns in Process List
- Added Read/s and Write/s columns to process list (columns 7 and 8)
- Uses existing `IOStats` module to collect per-process I/O data
- `format_rate()` method formats bytes/sec in human-readable format
- Sort functions for I/O rate columns
- Works in both list and tree view modes

#### System CPU Usage in Stats Bar
- Added CPU section to stats bar with circular indicator
- Shows CPU usage percentage from `/proc/stat`
- Displays load average (1 minute)
- New `get_cpu_usage()` method in `system_stats.py` calculates CPU percentage from jiffies

#### Process Signals Menu
- Right-click context menu now has "Send Signal" submenu
- Signals available: SIGSTOP, SIGCONT, SIGHUP, SIGINT
- Also added SIGKILL as "Force Kill" option
- `send_signal_to_selected()` method sends signals with toast feedback

#### Tree View Sort Functions Fix
- Added `_attach_sort_functions()` helper method
- Sort functions now reattached when switching between tree/list view modes
- Called in `_recreate_tree_view()` and `_recreate_list_view()`

