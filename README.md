# Process Manager

A modern, GTK4-based system process manager for Linux.

![Process Manager Screenshot](data/screenshots/main-window.png)

## Features

- **Process Monitoring**: View all running processes with detailed information
- **Resource Usage**: Monitor CPU and memory usage per process
- **GPU Monitoring**: Track GPU usage for Intel, NVIDIA, and AMD GPUs with per-process stats
- **Open Ports**: View all open network ports and connections with process information
- **Network Traffic**: Monitor bytes sent/received per connection with real-time rates
- **Process Bookmarks**: Bookmark frequently monitored processes for quick access
- **Process Comparison**: Compare selected processes with visual memory and CPU bars
- **System Stats**: Real-time memory, swap, disk, and GPU usage display with visual indicators
- **Process Control**: End processes with optional confirmation
- **Filter**: Quickly find processes by name, PID, or user
- **Sortable Columns**: Sort by Process Name, CPU, Memory, Started, User, Nice, or PID
- **Single Instance**: Only one instance of the app runs at a time
- **Modern UI**: Built with GTK4 and libadwaita for a native GNOME experience
- **Configurable**: Adjustable refresh interval, thresholds, and display options

## Installation

### Flatpak (Recommended)

```bash
# Install from Flathub (when published)
flatpak install flathub io.github.processmanager.ProcessManager

# Run
flatpak run io.github.processmanager.ProcessManager
```

### Build from Source with Flatpak

```bash
# Install Flatpak Builder
sudo apt install flatpak-builder

# Add Flathub repository
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install SDK
flatpak install flathub org.gnome.Platform//48 org.gnome.Sdk//48

# Build and install
flatpak-builder --user --install --force-clean build-dir io.github.processmanager.ProcessManager.json

# Run
flatpak run io.github.processmanager.ProcessManager
```

### Build from Source (System Install)

#### Dependencies

- Python 3.10+
- GTK 4.6+
- libadwaita 1.2+
- PyGObject 3.42+
- Meson 0.59+
- Ninja

#### Ubuntu/Debian

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
    meson ninja-build gettext libglib2.0-dev-bin
```

#### Fedora

```bash
sudo dnf install python3 python3-gobject gtk4 libadwaita python3-cairo \
    meson ninja-build gettext glib2-devel
```

#### Arch Linux

```bash
sudo pacman -S python python-gobject gtk4 libadwaita meson ninja gettext
```

#### Build & Install

```bash
meson setup build
meson compile -C build
sudo meson install -C build
```

## Development

### Running from Source

For development, you can run the application directly:

```bash
# Set up build directory
meson setup build

# Build
meson compile -C build

# Run (from the project root)
./build/src/process-manager
```

### Project Structure

```
process-manager/
├── src/
│   ├── __init__.py          # Package initialization with exports
│   ├── constants.py         # Application constants
│   ├── main.py              # Application entry point
│   ├── window.py            # Main window UI (ProcessManagerWindow)
│   ├── utils.py             # Utility functions (formatting, parsing)
│   ├── dialogs/             # Dialog classes
│   │   ├── __init__.py      # Re-exports all dialogs
│   │   ├── process_details.py   # Process details dialog
│   │   ├── renice.py        # Change priority dialog
│   │   ├── export.py        # Export process list dialog
│   │   ├── shortcuts.py     # Keyboard shortcuts window
│   │   └── termination.py   # Process termination dialog
│   ├── stats/               # Statistics package
│   │   ├── __init__.py      # Re-exports stats classes
│   │   ├── system.py        # System memory/cpu stats
│   │   ├── ports.py         # Port stats
│   │   ├── io.py            # I/O stats
│   │   └── gpu/             # GPU stats package
│   │       ├── __init__.py  # GPUStats facade
│   │       ├── nvidia.py    # NVIDIA implementation
│   │       ├── intel.py     # Intel implementation
│   │       └── amd.py       # AMD implementation
│   ├── ui/                  # UI components and mixins
│   │   ├── stats_bar.py     # Stats bar component
│   │   ├── selection_panel.py # Selection handling UI
│   │   ├── bookmarks_panel.py # Bookmarks UI
│   │   └── high_usage_panel.py # High resource usage alerts
│   ├── handlers/            # logic handlers
│   │   ├── keyboard.py      # Keyboard shortcuts handler
│   │   ├── context_menu.py  # Right-click menu handler
│   │   └── process_actions.py # Process control actions
│   ├── tabs/                # Tab mixin classes
│   │   ├── __init__.py      # Re-exports mixins
│   │   ├── gpu_tab.py       # GPU tab functionality
│   │   └── ports_tab.py     # Ports tab functionality
│   ├── process_manager.py   # Process management interface
│   ├── ps_commands.py       # PS command utilities for process info
│   ├── process_history.py   # Process lifecycle tracking
│   ├── settings.py          # Settings management
│   └── preferences.py       # Preferences dialog
├── data/
│   ├── icons/               # Application icons
│   ├── *.desktop.in         # Desktop entry
│   ├── *.metainfo.xml.in    # AppStream metadata
│   ├── *.gschema.xml        # GSettings schema
│   └── style.css            # Application styles (externalized)
├── po/                      # Translations
├── meson.build              # Build configuration
└── io.github.processmanager.ProcessManager.json  # Flatpak manifest
```

### Code Architecture

The application follows a modular architecture using the mixin pattern for separation of concerns:

**Core Modules:**
- **constants.py**: Centralized application constants including APP_ID and version
- **main.py**: Application class with GTK/Adwaita integration and CSS loading
- **window.py**: Main window class that inherits functionality from various mixins
- **process_manager.py**: High-level process operations (list, kill, renice)
- **utils.py**: Common utility functions for formatting and string parsing

**UI & Event Handling (Mixin Pattern):**
- **ui/**: Contains UI-specific mixins (`StatsBarMixin`, `SelectionPanelMixin`, `BookmarksPanelMixin`) that build and manage specific parts of the interface.
- **handlers/**: Contains logic mixins (`KeyboardHandlerMixin`, `ContextMenuMixin`, `ProcessActionsMixin`) that handle user input and actions multiple modular files.
- **tabs/**: Mixins for specific tabs (`GPUTabMixin`, `PortsTabMixin`).

**Statistics Package (`src/stats/`):**
- **system.py**: System memory, disk, and load average statistics
- **ports.py**: Open ports and network connections monitoring
- **io.py**: Per-process disk I/O statistics
- **gpu/**: Modular GPU monitoring subsystem
    - **base.py**: Abstract base class for GPU providers
    - **nvidia.py**: `nvidia-smi` based monitoring
    - **intel.py**: `intel_gpu_top` based monitoring
    - **amd.py**: `rocm-smi` and `radeontop` support

**Data & Settings:**
- **process_history.py**: Process lifecycle tracking and resource usage history
- **settings.py**: Persistent settings management with JSON storage
- **preferences.py**: User preferences dialog with categorized settings

All modules use type hints for improved code quality and IDE support.

## Configuration

Settings are stored in `~/.config/process-manager/settings.json` and include:

- **Refresh Interval**: Time between updates (500-10000ms)
- **Show Kernel Threads**: Include kernel threads in the list
- **Confirm Before Killing**: Show confirmation dialog before ending processes
- **CPU/Memory Thresholds**: Warning thresholds for highlighting
- **Theme**: System, Light, or Dark

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Delete` | End selected processes (SIGTERM) |
| `Shift+Delete` | Force kill selected processes (SIGKILL) |
| `Space` | Toggle auto-refresh (Play/Pause) |
| `Escape` | Close search / Clear selections |
| `Enter` | Select all filtered processes (in search mode) |
| `Ctrl+Tab` | Switch between Processes, GPU, and Ports tabs |
| `F5` | Refresh process list |
| `Ctrl+Q` | Quit application |
| `Ctrl+,` | Open preferences |
| `Ctrl+F` | Toggle filter/search bar |

## Publishing to Flathub

To publish this application to Flathub:

1. Fork [flathub/flathub](https://github.com/flathub/flathub)
2. Create a new branch with the app ID
3. Add the Flatpak manifest
4. Submit a pull request
5. Follow the [Flathub submission guidelines](https://github.com/flathub/flathub/wiki/App-Submission)

## License

This project is licensed under the GPL-3.0-or-later license. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Built with [GTK4](https://gtk.org/) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)
- Inspired by GNOME System Monitor and other task managers

