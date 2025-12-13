# SPDX-License-Identifier: GPL-3.0-or-later
# Bookmarks panel mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Pango


class BookmarksPanelMixin:
    """Mixin class providing bookmarks panel functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - settings: Settings instance
    - process_manager: ProcessManager instance
    - list_store: Gtk.ListStore
    - tree_view: Gtk.TreeView
    - format_memory: method
    """
    
    def create_bookmarks_panel(self):
        """Create the bookmarks panel showing bookmarked processes."""
        # Main container
        panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel_box.add_css_class("bookmarks-panel")
        
        # Header row with title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(8)
        header_box.set_margin_top(6)
        header_box.set_margin_bottom(4)
        
        # Title label
        self.bookmarks_title = Gtk.Label(label="Bookmarks:")
        self.bookmarks_title.add_css_class("heading")
        self.bookmarks_title.set_halign(Gtk.Align.START)
        self.bookmarks_title.set_hexpand(True)
        header_box.append(self.bookmarks_title)
        
        panel_box.append(header_box)
        
        # Scrolled window for bookmarks list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(150)
        scrolled.set_propagate_natural_height(True)
        
        # ListBox for bookmarks
        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.bookmarks_list.add_css_class("bookmarks-list")
        self.bookmarks_list.set_margin_start(12)
        self.bookmarks_list.set_margin_end(12)
        self.bookmarks_list.set_margin_bottom(8)
        self.bookmarks_list.connect("row-activated", self.on_bookmark_activated)
        scrolled.set_child(self.bookmarks_list)
        panel_box.append(scrolled)
        
        # Bottom separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        panel_box.append(sep)
        
        # Initially hidden
        panel_box.set_visible(False)
        
        return panel_box
    
    def update_bookmarks_panel(self):
        """Update the bookmarks panel with current bookmarked processes."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        count = len(bookmarked_pids)
        
        # Show/hide panel based on bookmarks
        self.bookmarks_panel.set_visible(count > 0)
        
        if count == 0:
            return
        
        # Update title
        self.bookmarks_title.set_label(f"Bookmarks ({count}):")
        
        # Clear existing rows
        while True:
            child = self.bookmarks_list.get_row_at_index(0)
            if child is None:
                break
            self.bookmarks_list.remove(child)
        
        # Get all processes to find bookmarked ones
        all_processes = self.process_manager.get_processes(
            show_all=True,
            my_processes=False,
            active_only=False,
            show_kernel_threads=True
        )
        process_map = {p['pid']: p for p in all_processes}
        
        # Add bookmarked processes
        for pid in bookmarked_pids:
            if pid in process_map:
                proc = process_map[pid]
                row = self.create_bookmark_row(proc)
                self.bookmarks_list.append(row)
            else:
                # Process no longer exists, remove from bookmarks
                bookmarked_pids.remove(pid)
                self.settings.set("bookmarked_pids", bookmarked_pids)
    
    def create_bookmark_row(self, proc):
        """Create a row for a bookmarked process."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        
        # Process name
        name_label = Gtk.Label(label=proc.get('name', 'Unknown'))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(name_label)
        
        # CPU and Memory
        cpu_str = f"{proc.get('cpu', 0):.1f}%"
        mem_str = self.format_memory(proc.get('memory', 0))
        info_label = Gtk.Label(label=f"{cpu_str} | {mem_str}")
        info_label.set_halign(Gtk.Align.END)
        info_label.add_css_class("dim-label")
        box.append(info_label)
        
        # Unbookmark button
        unbookmark_btn = Gtk.Button()
        unbookmark_btn.set_icon_name("bookmark-remove-symbolic")
        unbookmark_btn.set_tooltip_text("Unbookmark")
        unbookmark_btn.add_css_class("flat")
        unbookmark_btn.add_css_class("circular")
        unbookmark_btn.connect("clicked", lambda b, p=proc['pid']: self.toggle_bookmark(p))
        box.append(unbookmark_btn)
        
        row.set_child(box)
        return row
    
    def on_bookmark_activated(self, list_box, row):
        """Handle bookmark row activation - select the process in the main list."""
        box = row.get_child()
        # Find the name label to get process name
        for child in box:
            if isinstance(child, Gtk.Label) and child.get_halign() == Gtk.Align.START:
                name = child.get_text()
                # Find and select the process in the main list
                self._select_process_by_name(name)
                break
    
    def _select_process_by_name(self, name):
        """Select a process in the main list by name (selects first match)."""
        for i, row in enumerate(self.list_store):
            if row[0] == name:  # Process name column
                path = Gtk.TreePath.new_from_indices([i])
                selection = self.tree_view.get_selection()
                selection.select_path(path)
                self.tree_view.scroll_to_cell(path, None, False, 0, 0)
                break
    
    def toggle_bookmark(self, pid):
        """Toggle bookmark status for a process."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        if pid in bookmarked_pids:
            bookmarked_pids.remove(pid)
        else:
            bookmarked_pids.append(pid)
        self.settings.set("bookmarked_pids", bookmarked_pids)
        self.update_bookmarks_panel()
    
    def is_bookmarked(self, pid):
        """Check if a process is bookmarked."""
        bookmarked_pids = self.settings.get("bookmarked_pids", [])
        return pid in bookmarked_pids
