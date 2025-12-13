# SPDX-License-Identifier: GPL-3.0-or-later
# Renice dialog for changing process priority

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib


class ReniceDialog(Adw.Window):
    """Dialog for changing process priority (renice)."""
    
    def __init__(self, parent, process_manager, processes):
        """
        Args:
            parent: Parent window
            process_manager: ProcessManager instance
            processes: List of process dicts with 'pid', 'name', 'nice'
        """
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Change Process Priority",
            default_width=400,
            default_height=300,
        )
        
        self.process_manager = process_manager
        self.processes = processes
        self.parent = parent
        
        self.build_ui()
    
    def build_ui(self):
        """Build the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        main_box.append(content_box)
        
        # Process list
        if len(self.processes) == 1:
            proc = self.processes[0]
            label = Gtk.Label(label=f"Process: {proc['name']} (PID: {proc['pid']})")
        else:
            label = Gtk.Label(label=f"{len(self.processes)} processes selected")
        label.set_halign(Gtk.Align.START)
        content_box.append(label)
        
        # Current priority
        current_nice = self.processes[0]['nice']
        current_label = Gtk.Label(label=f"Current priority: {current_nice}")
        current_label.set_halign(Gtk.Align.START)
        content_box.append(current_label)
        
        # Priority adjustment
        adj_group = Adw.PreferencesGroup()
        adj_group.set_title("Priority (Nice Value)")
        content_box.append(adj_group)
        
        # Spin button for nice value (-20 to 19)
        nice_row = Adw.ActionRow()
        nice_row.set_title("Nice Value")
        
        adjustment = Gtk.Adjustment(value=current_nice, lower=-20, upper=19, step_increment=1)
        self.nice_spin = Gtk.SpinButton(adjustment=adjustment)
        self.nice_spin.set_numeric(True)
        nice_row.add_suffix(self.nice_spin)
        adj_group.add(nice_row)
        
        # Info label
        info_label = Gtk.Label()
        info_label.set_markup("<small>Range: -20 (highest priority) to 19 (lowest priority)</small>")
        info_label.set_halign(Gtk.Align.START)
        info_label.set_margin_start(24)
        info_label.set_margin_end(24)
        content_box.append(info_label)
        
        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        content_box.append(button_box)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        button_box.append(cancel_btn)
        
        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self.on_apply)
        button_box.append(apply_btn)
    
    def on_apply(self, button):
        """Apply the new nice value."""
        new_nice = int(self.nice_spin.get_value())
        
        success_count = 0
        failed = []
        
        for proc in self.processes:
            try:
                self.process_manager.renice_process(proc['pid'], new_nice)
                success_count += 1
            except Exception as e:
                failed.append(f"{proc['name']} (PID {proc['pid']}): {e}")
        
        if failed:
            error_msg = f"Failed to change priority for:\n" + "\n".join(failed)
            self.parent.show_error(error_msg)
        else:
            if len(self.processes) == 1:
                self.parent.show_error(f"Priority changed to {new_nice}")
            else:
                self.parent.show_error(f"Priority changed to {new_nice} for {success_count} processes")
        
        self.close()
        # Refresh after a short delay
        GLib.timeout_add(500, lambda: self.parent.refresh_processes())
