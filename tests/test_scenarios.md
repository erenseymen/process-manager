# Test Scenarios

## Search Feature Tests

### TC-001: Escape Key Closes Search Bar

**Description:** Verify that pressing the Escape key closes the search bar and clears the search text.

**Preconditions:**
- Application is running
- Search bar is closed

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
- Focus returns to the process list

**Status:** ✅ Passed

---

### TC-002: Search with Enter Key Selects All Filtered Processes

**Description:** Verify that pressing Enter in search selects all visible filtered processes.

**Preconditions:**
- Application is running

**Test Steps:**
1. Type a search term that matches multiple processes
2. Press Enter

**Expected Results:**
- All filtered processes are selected
- Search bar closes
- Search text is cleared
- Selected processes appear in selection panel

**Status:** ✅ Passed

---

### TC-003: Type-to-Search Opens Search Bar

**Description:** Verify that typing any printable character opens the search bar.

**Preconditions:**
- Application is running
- Search bar is closed
- Focus is on main window

**Test Steps:**
1. Press any letter key (e.g., "g")

**Expected Results:**
- Search bar opens automatically
- Typed character appears in search field
- Process list is filtered

**Status:** ✅ Passed

---

## Keyboard Shortcuts Summary

| Shortcut | Action | Status |
|----------|--------|--------|
| `Escape` | Close search bar | ✅ |
| `Enter` (in search) | Select all filtered & close | ✅ |
| Any letter | Open search & type | ✅ |
| `Ctrl+F` | Toggle filter | ✅ |
| `Ctrl+Q` | Quit application | ✅ |
| `Ctrl+,` | Open preferences | ✅ |
| `F5` | Refresh process list | ✅ |
