# SPDX-License-Identifier: GPL-3.0-or-later
# Process details dialog

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Pango, Gdk


class ProcessDetailsDialog(Adw.Window):
    """Dialog for displaying detailed process information with copyable fields."""
    
    def __init__(self, parent, process_manager, pid, process_info):
        """
        Args:
            parent: Parent window
            process_manager: ProcessManager instance
            pid: Process ID
            process_info: Dict with basic process info (name, cpu_str, mem_str, user, etc.)
        """
        super().__init__(
            transient_for=parent,
            modal=True,
            title=f"Process Details - {process_info.get('name', 'Unknown')} (PID: {pid})",
            default_width=600,
            default_height=500,
        )
        
        self.process_manager = process_manager
        self.pid = pid
        self.process_info = process_info
        
        self.build_ui()
    
    def build_ui(self):
        """Build the dialog UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Scrolled content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # Content box with margins
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        scrolled.set_child(content_box)
        main_box.append(scrolled)
        
        # Get detailed process info
        details = self.process_manager.get_process_details(self.pid)
        
        # Basic info group
        basic_group = Adw.PreferencesGroup()
        basic_group.set_title("Basic Information")
        content_box.append(basic_group)
        
        # PID
        self.add_copyable_row(basic_group, "PID", str(self.pid))
        
        # Name
        self.add_copyable_row(basic_group, "Name", self.process_info.get('name', 'Unknown'))
        
        # User
        self.add_copyable_row(basic_group, "User", self.process_info.get('user', 'N/A'))
        
        # State
        self.add_copyable_row(basic_group, "State", self.process_info.get('state', 'N/A'))
        
        # CPU
        self.add_copyable_row(basic_group, "CPU", self.process_info.get('cpu_str', 'N/A'))
        
        # Memory
        self.add_copyable_row(basic_group, "Memory", self.process_info.get('mem_str', 'N/A'))
        
        # Nice
        self.add_copyable_row(basic_group, "Nice", str(self.process_info.get('nice', 'N/A')))
        
        # Started
        self.add_copyable_row(basic_group, "Started", self.process_info.get('started', 'N/A'))
        
        # Execution info group
        exec_group = Adw.PreferencesGroup()
        exec_group.set_title("Execution Details")
        content_box.append(exec_group)
        
        # Command line
        self.add_copyable_row(exec_group, "Command Line", details.get('cmdline', 'N/A'), multiline=True)
        
        # Executable path
        self.add_copyable_row(exec_group, "Executable", details.get('exe', 'N/A'))
        
        # Current working directory
        self.add_copyable_row(exec_group, "Working Directory", details.get('cwd', 'N/A'))
        
        # Resource info group
        resource_group = Adw.PreferencesGroup()
        resource_group.set_title("Resources")
        content_box.append(resource_group)
        
        # Threads
        self.add_copyable_row(resource_group, "Threads", str(details.get('threads', 'N/A')))
        
        # File descriptors
        self.add_copyable_row(resource_group, "File Descriptors", str(details.get('fd_count', 'N/A')))
        
        # Environment variables group (if available)
        environ = details.get('environ', '')
        if environ and environ != 'N/A':
            env_group = Adw.PreferencesGroup()
            env_group.set_title("Environment Variables")
            content_box.append(env_group)
            
            # Show environment in a text view
            self.add_copyable_row(env_group, "Environment", environ, multiline=True, max_lines=10)
        
        # Add key controller for keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
    
    def add_copyable_row(self, group, label, value, multiline=False, max_lines=3):
        """Add a row with a copyable value field."""
        row = Adw.ActionRow()
        row.set_title(label)
        
        if multiline:
            # For multiline content, use a text view with copy button
            multiline_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            multiline_box.set_hexpand(True)
            
            # Text view for multiline content
            text_view = Gtk.TextView()
            text_view.set_editable(False)
            text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            text_view.get_buffer().set_text(value)
            text_view.set_monospace(True)
            text_view.add_css_class("card")
            text_view.set_cursor_visible(False)
            
            # Calculate height based on content
            lines = value.count('\n') + 1
            display_lines = min(lines, max_lines)
            text_view.set_size_request(-1, display_lines * 20 + 12)
            
            # Wrap in scrolled window if content exceeds max_lines
            if lines > max_lines:
                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scroll.set_max_content_height(max_lines * 20 + 12)
                scroll.set_child(text_view)
                scroll.set_hexpand(True)
                multiline_box.append(scroll)
            else:
                text_view.set_hexpand(True)
                multiline_box.append(text_view)
            
            # Copy button for multiline content
            copy_btn = Gtk.Button()
            copy_btn.set_icon_name("edit-copy-symbolic")
            copy_btn.set_tooltip_text("Copy to clipboard")
            copy_btn.add_css_class("flat")
            copy_btn.add_css_class("circular")
            copy_btn.set_valign(Gtk.Align.START)
            copy_btn.set_margin_top(4)
            copy_btn.connect("clicked", lambda b, v=value: self.copy_to_clipboard(v))
            multiline_box.append(copy_btn)
            
            row.add_suffix(multiline_box)
        else:
            # Single line - use label with copy button
            value_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            value_box.set_hexpand(True)
            value_box.set_halign(Gtk.Align.END)
            
            value_label = Gtk.Label(label=value)
            value_label.set_selectable(True)
            value_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            value_label.set_max_width_chars(40)
            value_label.set_xalign(1)
            value_label.add_css_class("monospace")
            value_box.append(value_label)
            
            # Copy button
            copy_btn = Gtk.Button()
            copy_btn.set_icon_name("edit-copy-symbolic")
            copy_btn.set_tooltip_text("Copy to clipboard")
            copy_btn.add_css_class("flat")
            copy_btn.add_css_class("circular")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.connect("clicked", lambda b, v=value: self.copy_to_clipboard(v))
            value_box.append(copy_btn)
            
            row.add_suffix(value_box)
        
        group.add(row)
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape: close the dialog
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True  # Event handled
        
        return False  # Let other handlers process
