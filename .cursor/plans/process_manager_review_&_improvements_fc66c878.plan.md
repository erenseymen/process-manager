---
name: Process Manager Review & Improvements
overview: Comprehensive review of the Process Manager codebase identifying bug fixes and suggesting new features to enhance functionality and user experience.
todos:
  - id: fix-error-toast
    content: Fix show_error() to display toast overlay instead of just printing to console
    status: pending
  - id: fix-gpu-thread-cleanup
    content: Improve GPU background thread cleanup to prevent race conditions on exit
    status: pending
  - id: fix-port-parsing
    content: Improve port parsing to handle IPv6 addresses with brackets and edge cases
    status: pending
  - id: add-window-size-persistence
    content: Implement window size/position saving and restoration on startup
    status: pending
  - id: improve-error-handling
    content: Add better error handling for process details, especially permission errors
    status: pending
  - id: process-tree-view
    content: Implement process tree view showing parent-child relationships
    status: pending
  - id: process-renice-ui
    content: Add UI for changing process priority (renice) with dialog and context menu
    status: pending
  - id: export-functionality
    content: Add export to CSV/JSON/text for process lists with column selection
    status: pending
  - id: advanced-search
    content: Implement advanced filter dialog with multiple criteria and saved presets
    status: pending
  - id: io-statistics
    content: Add I/O statistics tab showing disk and network I/O per process
    status: pending
---

# Process Manager Review & Improvements

## Bug Fixes

### Critical Issues

1. **Error Toast Not Displayed** (`src/window.py:2768-2772`)

- `show_error()` method only prints to console, doesn't show UI toast
- Need to add `Adw.ToastOverlay` to window and properly display toasts
- Affects user experience when process operations fail

2. **Missing Error Handling in Process Details** (`src/ps_commands.py:178-184`)

- Reading `/proc/{pid}/environ` can fail for processes without permission
- Should handle permission errors gracefully instead of showing "N/A"
- Consider showing partial environment or permission message

3. **Race Condition in GPU Background Thread** (`src/gpu_stats.py:210-221`)

- Background thread may continue after window is closed
- `stop_background_updates()` has 2s timeout which may not be enough
- Should ensure proper cleanup on application exit

4. **Port Parsing Edge Cases** (`src/port_stats.py:58-134`)

- Regex patterns may not match all `ss` output formats
- IPv6 addresses with brackets not handled: `[::1]:8080`
- Should add more robust parsing with fallbacks

5. **Process Selection Cleanup** (`src/window.py:2135-2138`)

- Selected processes removed when they exit, but no user notification
- Should show toast when selected processes disappear
- Selection panel may show stale data briefly

### Minor Issues

6. **PS Output Parsing** (`src/ps_commands.py:78-99`)

- `lstart` field parsing assumes fixed format, may break with long process names
- Process names with spaces could break column parsing
- Should use more robust parsing or different ps format

7. **Intel GPU Top Timeout** (`src/gpu_stats.py:524`)

- Uses `sudo -n` which requires passwordless sudo
- No fallback if sudo fails, silently returns None
- Should detect and inform user about sudo requirements

8. **Settings File Corruption** (`src/settings.py:48-59`)

- If JSON file is corrupted, silently falls back to defaults
- Should backup corrupted file and notify user
- No validation of setting values (e.g., refresh_interval could be negative)

9. **Memory Calculation** (`src/system_stats.py:71-72`)

- `mem_used = mem_total - mem_available` may not match system tools
- Different systems calculate "used" differently
- Should document calculation method or add option

10. **Window Size Not Saved** (`src/settings.py:36-37`)

- Window width/height settings exist but not used
- Window size not persisted between sessions
- Should restore window geometry on startup

## New Features

### High Priority Features

1. **Process Tree View**

- Show parent-child relationships between processes
- Expandable tree structure in process list
- Filter by process tree branch
- Visual indicators for process hierarchy

2. **Process Renice/Priority UI**

- Right-click context menu option to change nice value
- Dialog to set priority (-20 to 19)
- Visual indicator of process priority in list
- Batch renice for selected processes

3. **Export Process List**

- Export to CSV, JSON, or plain text
- Include selected columns only
- Export filtered/selected processes
- Menu option: File → Export

4. **Improved Search/Filter**

- Advanced filter dialog with multiple criteria
- Save/load filter presets
- Filter by CPU range, memory range, user, state
- Regular expression support in search

5. **Process I/O Statistics**

- New tab or columns showing disk I/O (read/write bytes, IOPS)
- Network I/O per process
- Real-time I/O rate monitoring
- Top I/O processes panel

### Medium Priority Features

6. **Process History/Logging**

- Track process start/stop events
- Log process resource usage over time
- View process lifetime statistics
- Export process history

7. **Custom Columns**

- User-configurable column visibility
- Add custom columns (e.g., PPID, TTY, CMD)
- Save column layout preferences
- Drag-and-drop column reordering

8. **Process Alerts/Notifications**

- Alert when process exceeds CPU/memory thresholds
- Desktop notifications for high resource usage
- Sound alerts (optional)
- Configurable alert rules

9. **Network Traffic Monitoring**

- Enhanced ports tab with traffic statistics
- Bytes sent/received per connection
- Network usage graphs
- Top network processes

10. **Process Dependencies**

- Show shared libraries loaded by process
- File handles/open files per process
- Network connections per process (enhanced)
- Process resource dependencies

11. **Batch Operations**

- Select multiple processes with checkboxes
- Batch kill, renice, or change priority
- Save process selection sets
- Quick actions toolbar

12. **System Information Panel**

- Enhanced system stats with more details
- CPU temperature (if available)
- Disk I/O statistics
- Network interface statistics
- System load history graph

### Low Priority / Nice-to-Have Features

13. **Process Comparison Tool**

- Compare two processes side-by-side
- Diff view of process details
- Resource usage comparison graphs

14. **Process Templates/Profiles**

- Save process configurations
- Quick launch with specific nice values
- Process monitoring profiles

15. **Dark/Light Theme Toggle**

- Quick theme switcher in header
- Per-window theme (if multiple windows supported)
- Auto theme based on time of day

16. **Keyboard Navigation Improvements**

- Vim-like navigation (j/k for up/down)
- Quick filter with `/` key
- Number keys for quick actions

17. **Process Bookmarks**

- Bookmark frequently monitored processes
- Quick access panel for bookmarked processes
- Alerts for bookmarked processes only

18. **Multi-Monitor Support**

- Detached stats panels
- Move tabs to separate windows
- Customizable panel layouts

## Implementation Priority

### Phase 1 (Critical Bug Fixes)

- Fix error toast display
- Improve error handling in process details
- Fix GPU thread cleanup
- Add window size persistence

**Copy this prompt for Phase 1:**

```
Implement Phase 1 bug fixes for Process Manager:

1. Fix error toast display (src/window.py:2768-2772) - Add Adw.ToastOverlay to window and properly display error toasts instead of just printing to console

2. Improve error handling in process details (src/ps_commands.py:178-184) - Handle permission errors gracefully when reading /proc/{pid}/environ, show partial environment or permission message instead of "N/A"

3. Fix GPU thread cleanup (src/gpu_stats.py:210-221) - Ensure background thread properly stops on window close, prevent race conditions on application exit

4. Add window size persistence (src/settings.py:36-37, src/window.py) - Save and restore window size/position on startup using existing settings

5. Improve port parsing (src/port_stats.py:58-134) - Handle IPv6 addresses with brackets like [::1]:8080 and add more robust parsing with fallbacks

6. Add notification when selected processes exit (src/window.py:2135-2138) - Show toast when selected processes disappear from the list

Read the codebase context in docs/ai-context.md and follow existing patterns. Test all fixes thoroughly.
```

---

### Phase 2 (High Priority Features)

- Process tree view
- Process renice UI
- Export functionality
- Improved search/filter

**Copy this prompt for Phase 2:**

```
Implement Phase 2 high priority features for Process Manager:

1. Process Tree View - Add expandable tree structure showing parent-child relationships between processes. Include visual indicators for hierarchy and ability to filter by process tree branch. Modify the process list to support tree view mode.

2. Process Renice/Priority UI - Add right-click context menu option to change nice value. Create dialog to set priority (-20 to 19). Add visual indicator of process priority in the process list. Support batch renice for selected processes.

3. Export Process List - Add export functionality to CSV, JSON, and plain text formats. Allow exporting selected columns only and filtered/selected processes. Add menu option: File → Export.

4. Improved Search/Filter - Create advanced filter dialog with multiple criteria (CPU range, memory range, user, state). Add ability to save/load filter presets. Add regular expression support in search.

Read the codebase context in docs/ai-context.md and follow existing patterns. Ensure all features integrate well with existing UI and settings system.
```

---

### Phase 3 (Medium Priority)

- I/O statistics
- Process history
- Custom columns
- Process alerts

**Copy this prompt for Phase 3:**

```
Implement Phase 3 medium priority features for Process Manager:

1. Process I/O Statistics - Add new tab or columns showing disk I/O (read/write bytes, IOPS) and network I/O per process. Include real-time I/O rate monitoring and a "Top I/O processes" panel.

2. Process History/Logging - Track process start/stop events and log process resource usage over time. Add UI to view process lifetime statistics and export process history.

3. Custom Columns - Implement user-configurable column visibility. Add ability to add custom columns (e.g., PPID, TTY, CMD). Save column layout preferences and support drag-and-drop column reordering.

4. Process Alerts/Notifications - Add alerts when processes exceed CPU/memory thresholds. Implement desktop notifications for high resource usage with optional sound alerts. Create configurable alert rules in preferences.

Read the codebase context in docs/ai-context.md and follow existing patterns. Ensure performance is maintained with new monitoring features.
```

---

### Phase 4 (Polish & Enhancements)

- Remaining features based on user feedback
- Performance optimizations
- UI/UX improvements

**Copy this prompt for Phase 4:**

```
Implement Phase 4 polish and enhancements for Process Manager:

Review the remaining features from the plan and implement based on priority:
- Network Traffic Monitoring (enhanced ports tab with traffic statistics)
- Process Dependencies (shared libraries, file handles, connections)
- Batch Operations (checkboxes, batch actions, selection sets)
- System Information Panel (enhanced stats, CPU temp, disk I/O, network interfaces)
- Process Comparison Tool
- Process Templates/Profiles
- Keyboard Navigation Improvements (vim-like navigation)
- Process Bookmarks
- Multi-Monitor Support

Also focus on:
- Performance optimizations for large process lists
- UI/UX improvements based on usability
- Code cleanup and refactoring
- Documentation updates

Read the codebase context in docs/ai-context.md and follow existing patterns. Prioritize features that provide the most value to users.
```