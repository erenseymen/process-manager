# SPDX-License-Identifier: GPL-3.0-or-later
# Preferences dialog

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw


class PreferencesDialog(Adw.PreferencesWindow):
    """Application preferences dialog."""
    
    def __init__(self, parent, settings):
        super().__init__(
            transient_for=parent,
            title="Preferences",
            modal=True
        )
        
        self.settings = settings
        self.build_ui()
    
    def build_ui(self):
        """Build the preferences UI."""
        # General page
        general_page = Adw.PreferencesPage()
        general_page.set_title("General")
        general_page.set_icon_name("preferences-system-symbolic")
        self.add(general_page)
        
        # Behavior group
        behavior_group = Adw.PreferencesGroup()
        behavior_group.set_title("Behavior")
        behavior_group.set_description("Configure application behavior")
        general_page.add(behavior_group)
        
        # Refresh interval
        refresh_row = Adw.SpinRow.new_with_range(500, 10000, 100)
        refresh_row.set_title("Refresh Interval")
        refresh_row.set_subtitle("Time between process list updates (milliseconds)")
        refresh_row.set_value(self.settings.get("refresh_interval"))
        refresh_row.connect("notify::value", self.on_refresh_changed)
        behavior_group.add(refresh_row)
        
        # Confirm kill
        confirm_row = Adw.SwitchRow()
        confirm_row.set_title("Confirm Before Killing")
        confirm_row.set_subtitle("Show confirmation dialog before ending processes")
        confirm_row.set_active(self.settings.get("confirm_kill"))
        confirm_row.connect("notify::active", self.on_confirm_changed)
        behavior_group.add(confirm_row)
        
        # Display group
        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display")
        display_group.set_description("Configure what processes to show")
        general_page.add(display_group)
        
        # Show all processes
        all_proc_row = Adw.SwitchRow()
        all_proc_row.set_title("Show All Processes")
        all_proc_row.set_subtitle("Show processes from all users")
        all_proc_row.set_active(self.settings.get("show_all_processes"))
        all_proc_row.connect("notify::active", self.on_show_all_changed)
        display_group.add(all_proc_row)
        
        # Show kernel threads
        kernel_row = Adw.SwitchRow()
        kernel_row.set_title("Show Kernel Threads")
        kernel_row.set_subtitle("Show kernel threads in the process list")
        kernel_row.set_active(self.settings.get("show_kernel_threads"))
        kernel_row.connect("notify::active", self.on_kernel_changed)
        display_group.add(kernel_row)
        
        # Appearance page
        appearance_page = Adw.PreferencesPage()
        appearance_page.set_title("Appearance")
        appearance_page.set_icon_name("applications-graphics-symbolic")
        self.add(appearance_page)
        
        # Theme group
        theme_group = Adw.PreferencesGroup()
        theme_group.set_title("Theme")
        appearance_page.add(theme_group)
        
        # Theme selection
        theme_row = Adw.ComboRow()
        theme_row.set_title("Color Scheme")
        theme_row.set_subtitle("Choose the application color scheme")
        
        theme_model = Gtk.StringList()
        theme_model.append("System")
        theme_model.append("Light")
        theme_model.append("Dark")
        theme_row.set_model(theme_model)
        
        current_theme = self.settings.get("theme")
        theme_idx = {"system": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        theme_row.set_selected(theme_idx)
        theme_row.connect("notify::selected", self.on_theme_changed)
        theme_group.add(theme_row)
        
        # Thresholds page
        thresholds_page = Adw.PreferencesPage()
        thresholds_page.set_title("Thresholds")
        thresholds_page.set_icon_name("dialog-warning-symbolic")
        self.add(thresholds_page)
        
        # Warning thresholds group
        warning_group = Adw.PreferencesGroup()
        warning_group.set_title("Warning Thresholds")
        warning_group.set_description("Set thresholds for highlighting high resource usage")
        thresholds_page.add(warning_group)
        
        # CPU threshold
        cpu_row = Adw.SpinRow.new_with_range(10, 100, 5)
        cpu_row.set_title("CPU Warning Threshold")
        cpu_row.set_subtitle("Highlight processes using more than this CPU percentage")
        cpu_row.set_value(self.settings.get("cpu_threshold_warning"))
        cpu_row.connect("notify::value", self.on_cpu_threshold_changed)
        warning_group.add(cpu_row)
        
        # Memory threshold
        mem_row = Adw.SpinRow.new_with_range(10, 100, 5)
        mem_row.set_title("Memory Warning Threshold")
        mem_row.set_subtitle("Highlight processes using more than this memory percentage")
        mem_row.set_value(self.settings.get("memory_threshold_warning"))
        mem_row.connect("notify::value", self.on_mem_threshold_changed)
        warning_group.add(mem_row)
        
        # About section
        about_group = Adw.PreferencesGroup()
        about_group.set_title("About")
        general_page.add(about_group)
        
        # Reset to defaults
        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset to Defaults")
        reset_row.set_subtitle("Restore all settings to their default values")
        
        reset_button = Gtk.Button(label="Reset")
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.add_css_class("destructive-action")
        reset_button.connect("clicked", self.on_reset_clicked)
        reset_row.add_suffix(reset_button)
        reset_row.set_activatable_widget(reset_button)
        about_group.add(reset_row)
    
    def on_refresh_changed(self, row, param):
        """Handle refresh interval change."""
        self.settings.set("refresh_interval", int(row.get_value()))
    
    def on_confirm_changed(self, row, param):
        """Handle confirm kill change."""
        self.settings.set("confirm_kill", row.get_active())
    
    def on_show_all_changed(self, row, param):
        """Handle show all processes change."""
        self.settings.set("show_all_processes", row.get_active())
    
    def on_kernel_changed(self, row, param):
        """Handle show kernel threads change."""
        self.settings.set("show_kernel_threads", row.get_active())
    
    def on_theme_changed(self, row, param):
        """Handle theme change."""
        themes = ["system", "light", "dark"]
        selected = row.get_selected()
        self.settings.set("theme", themes[selected])
        
        # Apply theme immediately
        style_manager = Adw.StyleManager.get_default()
        if themes[selected] == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif themes[selected] == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
    
    def on_cpu_threshold_changed(self, row, param):
        """Handle CPU threshold change."""
        self.settings.set("cpu_threshold_warning", int(row.get_value()))
    
    def on_mem_threshold_changed(self, row, param):
        """Handle memory threshold change."""
        self.settings.set("memory_threshold_warning", int(row.get_value()))
    
    def on_reset_clicked(self, button):
        """Handle reset to defaults."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Reset Settings?",
            body="This will restore all settings to their default values."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_reset_response)
        dialog.present()
    
    def on_reset_response(self, dialog, response):
        """Handle reset confirmation response."""
        if response == "reset":
            self.settings.reset()
            self.close()

