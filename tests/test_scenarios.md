# Test Scenarios

## Search Feature Tests

### TC-001: Escape Key Closes Search Bar

**Description:** Verify that pressing the Escape key closes the search bar and clears the search text.

**Preconditions:**
- Application is running
- Search bar is closed
- Focus is on main window or process list

**Test Steps:**
1. Type any character (e.g., "f") to open the search bar
2. Verify search bar opens and character appears in search field
3. Type additional characters (e.g., "irefox")
4. Verify processes are filtered based on search text
5. Press the Escape key

**Expected Results:**
- Search bar closes
- Search text is cleared
- Process list shows all processes (unfiltered)
- Focus returns to the process list (tree view)

**Status:** ✅ Passed

---

### TC-002: Search with Enter Key Selects All Filtered Processes

**Description:** Verify that pressing Enter in search selects all visible filtered processes and closes the search bar.

**Preconditions:**
- Application is running
- Search bar is open or can be opened

**Test Steps:**
1. Type a search term that matches multiple processes (e.g., "firefox")
2. Verify processes are filtered based on search text
3. Press Enter while search entry has focus

**Expected Results:**
- All currently visible (filtered) processes are selected
- Search bar closes
- Search text is cleared
- Selected processes appear in selection panel
- Focus returns to the process list (tree view)

**Status:** ✅ Passed

---

### TC-003: Type-to-Search Opens Search Bar

**Description:** Verify that typing any printable character opens the search bar and appends the character to the search field.

**Preconditions:**
- Application is running
- Search bar is closed
- Focus is on main window (not in search entry)

**Test Steps:**
1. Press any printable character key (e.g., "g")

**Expected Results:**
- Search bar opens automatically
- Typed character appears in search field
- Process list is filtered based on the typed character
- Search entry has focus

**Status:** ✅ Passed

---

### TC-004: Type-to-Search Appends to Existing Text

**Description:** Verify that typing characters when search bar is already open appends to existing text.

**Preconditions:**
- Application is running
- Search bar is open with existing text (e.g., "fire")

**Test Steps:**
1. Type additional characters (e.g., "fox")

**Expected Results:**
- New characters are appended to existing search text
- Process list is filtered based on the complete search text
- Cursor is positioned at the end of the text

**Status:** ✅ Passed

---

### TC-005: Ctrl+F Toggles Search Bar

**Description:** Verify that Ctrl+F toggles the search bar (opens if closed, closes if open).

**Preconditions:**
- Application is running

**Test Steps:**
1. Press Ctrl+F
2. Verify search bar opens
3. Press Ctrl+F again
4. Verify search bar closes

**Expected Results:**
- First Ctrl+F: Search bar opens, search entry receives focus
- Second Ctrl+F: Search bar closes, search text is cleared, focus returns to process list

**Status:** ✅ Passed

---

### TC-006: Ctrl+F Closes Search Bar with Text

**Description:** Verify that Ctrl+F closes the search bar even when it contains text.

**Preconditions:**
- Application is running
- Search bar is open with text (e.g., "firefox")

**Test Steps:**
1. Press Ctrl+F

**Expected Results:**
- Search bar closes
- Search text is cleared
- Process list shows all processes (unfiltered)
- Focus returns to process list

**Status:** ✅ Passed

---

## Process Control Tests

### TC-007: Delete Key Terminates Selected Processes

**Description:** Verify that Delete key sends SIGTERM to selected processes.

**Preconditions:**
- Application is running
- One or more processes are selected

**Test Steps:**
1. Select one or more processes in the process list
2. Press Delete key

**Expected Results:**
- If "Confirm Before Killing" is enabled: Confirmation dialog appears
- If "Confirm Before Killing" is disabled: Processes are terminated immediately
- Selected processes receive SIGTERM signal
- Process list is refreshed after termination

**Status:** ✅ Passed

---

### TC-008: Shift+Delete Force Kills Selected Processes

**Description:** Verify that Shift+Delete sends SIGKILL to selected processes.

**Preconditions:**
- Application is running
- One or more processes are selected

**Test Steps:**
1. Select one or more processes in the process list
2. Press Shift+Delete

**Expected Results:**
- If "Confirm Before Killing" is enabled: Confirmation dialog appears
- If "Confirm Before Killing" is disabled: Processes are force killed immediately
- Selected processes receive SIGKILL signal
- Process list is refreshed after termination

**Status:** ✅ Passed

---

### TC-009: Delete Key Does Nothing When No Selection

**Description:** Verify that Delete key has no effect when no processes are selected.

**Preconditions:**
- Application is running
- No processes are selected

**Test Steps:**
1. Ensure no processes are selected
2. Press Delete key

**Expected Results:**
- No action occurs
- No processes are terminated
- No dialog appears

**Status:** ✅ Passed

---

## Auto-Refresh Tests

### TC-010: Space Key Toggles Auto-Refresh

**Description:** Verify that Space key toggles the auto-refresh Play/Pause button.

**Preconditions:**
- Application is running
- Focus is on main window (not in search entry)

**Test Steps:**
1. Verify auto-refresh is currently running (Play/Pause button shows pause icon)
2. Press Space key
3. Verify auto-refresh is paused (button shows play icon)
4. Press Space key again
5. Verify auto-refresh resumes (button shows pause icon)

**Expected Results:**
- First Space: Auto-refresh pauses, button icon changes to play
- Second Space: Auto-refresh resumes, button icon changes to pause
- Process list stops/starts updating accordingly

**Status:** ✅ Passed

---

### TC-011: Space Key Does Not Toggle When Search Is Focused

**Description:** Verify that Space key does not toggle auto-refresh when search entry has focus.

**Preconditions:**
- Application is running
- Search bar is open and search entry has focus

**Test Steps:**
1. Open search bar and ensure search entry has focus
2. Press Space key

**Expected Results:**
- Space character is inserted into search field
- Auto-refresh state does not change
- Play/Pause button state remains unchanged

**Status:** ✅ Passed

---

## Process Details Tests

### TC-012: Enter Key Shows Process Details

**Description:** Verify that Enter key opens process details dialog for selected process.

**Preconditions:**
- Application is running
- At least one process is selected
- Search bar is not active or not focused

**Test Steps:**
1. Select a process in the process list
2. Press Enter key

**Expected Results:**
- Process details dialog opens
- Dialog shows detailed information about the selected process
- Dialog can be closed with Escape or Close button

**Status:** ✅ Passed

---

## Tab Navigation Tests

### TC-013: Ctrl+Tab Switches Between Tabs

**Description:** Verify that Ctrl+Tab switches between Processes and GPU tabs.

**Preconditions:**
- Application is running
- Currently on Processes tab

**Test Steps:**
1. Press Ctrl+Tab
2. Verify tab switches to GPU
3. Press Ctrl+Tab again
4. Verify tab switches back to Processes

**Expected Results:**
- First Ctrl+Tab: Switches from Processes to GPU tab
- Second Ctrl+Tab: Switches from GPU to Processes tab
- Appropriate process list is displayed for each tab

**Status:** ✅ Passed

---

## Application Actions Tests

### TC-014: F5 Refreshes Process List

**Description:** Verify that F5 key manually refreshes the current tab's process list.

**Preconditions:**
- Application is running
- On Processes or GPU tab

**Test Steps:**
1. Note the current process list state
2. Press F5 key
3. Verify process list is refreshed

**Expected Results:**
- Process list is immediately refreshed
- Updated process information is displayed
- Works on both Processes and GPU tabs

**Status:** ✅ Passed

---

### TC-015: Ctrl+Q Quits Application

**Description:** Verify that Ctrl+Q quits the application.

**Preconditions:**
- Application is running

**Test Steps:**
1. Press Ctrl+Q

**Expected Results:**
- Application quits
- Window closes
- Application process terminates

**Status:** ✅ Passed

---

### TC-016: Ctrl+, Opens Preferences

**Description:** Verify that Ctrl+, opens the preferences dialog.

**Preconditions:**
- Application is running

**Test Steps:**
1. Press Ctrl+,

**Expected Results:**
- Preferences dialog opens
- Dialog shows all preference categories
- Dialog can be closed with Escape or Close button

**Status:** ✅ Passed

---

## Keyboard Shortcuts Summary

| Shortcut | Action | Status |
|----------|--------|--------|
| `Escape` | Close search bar and clear text | ✅ |
| `Enter` (in search) | Select all filtered processes & close search | ✅ |
| `Enter` (in tree view) | Show process details for selected process | ✅ |
| Any printable character | Open search bar & type character | ✅ |
| `Ctrl+F` | Toggle search bar (open/close) | ✅ |
| `Space` | Toggle auto-refresh (Play/Pause) | ✅ |
| `Delete` | Terminate selected processes (SIGTERM) | ✅ |
| `Shift+Delete` | Force kill selected processes (SIGKILL) | ✅ |
| `Ctrl+Tab` | Switch between Processes and GPU tabs | ✅ |
| `F5` | Refresh process list | ✅ |
| `Ctrl+Q` | Quit application | ✅ |
| `Ctrl+,` | Open preferences | ✅ |
