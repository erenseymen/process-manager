# SPDX-License-Identifier: GPL-3.0-or-later
# Preferences dialog

"""Preferences dialog for configuring application settings."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

if TYPE_CHECKING:
    from .settings import Settings


class PreferencesDialog(Adw.PreferencesWindow):
    """Application preferences dialog.
    
    Provides UI for configuring refresh interval, display options,
    theme settings, warning thresholds, and alert rules.
    """
    
    def __init__(self, parent: Gtk.Window, settings: Settings) -> None:
        super().__init__(
            transient_for=parent,
            title="Preferences",
            modal=True
        )
        
        self.settings = settings
        self._alert_rows: Dict[str, Adw.ActionRow] = {}  # rule_id -> row
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the preferences UI."""
        self._build_general_page()
        self._build_appearance_page()
        self._build_thresholds_page()
        self._build_alerts_page()
    
    def _build_general_page(self) -> None:
        """Build the General preferences page."""
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
        refresh_row.connect("notify::value", self._on_refresh_changed)
        behavior_group.add(refresh_row)
        
        # Confirm kill
        confirm_row = Adw.SwitchRow()
        confirm_row.set_title("Confirm Before Killing")
        confirm_row.set_subtitle("Show confirmation dialog before ending processes")
        confirm_row.set_active(self.settings.get("confirm_kill"))
        confirm_row.connect("notify::active", self._on_confirm_changed)
        behavior_group.add(confirm_row)
        
        # Display group
        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display")
        display_group.set_description("Configure what processes to show")
        general_page.add(display_group)
        
        # Show kernel threads
        kernel_row = Adw.SwitchRow()
        kernel_row.set_title("Show Kernel Threads")
        kernel_row.set_subtitle("Show kernel threads in the process list")
        kernel_row.set_active(self.settings.get("show_kernel_threads"))
        kernel_row.connect("notify::active", self._on_kernel_changed)
        display_group.add(kernel_row)
        
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
        reset_button.connect("clicked", self._on_reset_clicked)
        reset_row.add_suffix(reset_button)
        reset_row.set_activatable_widget(reset_button)
        about_group.add(reset_row)
    
    def _build_appearance_page(self) -> None:
        """Build the Appearance preferences page."""
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
        theme_row.connect("notify::selected", self._on_theme_changed)
        theme_group.add(theme_row)
    
    def _build_thresholds_page(self) -> None:
        """Build the Thresholds preferences page."""
        thresholds_page = Adw.PreferencesPage()
        thresholds_page.set_title("Thresholds")
        thresholds_page.set_icon_name("dialog-warning-symbolic")
        self.add(thresholds_page)
        
        # Change detection thresholds group
        change_group = Adw.PreferencesGroup()
        change_group.set_title("Change Detection")
        change_group.set_description("Show processes when their resource usage changes by these amounts")
        thresholds_page.add(change_group)
        
        # CPU change threshold
        cpu_change_row = Adw.SpinRow.new_with_range(1, 50, 1)
        cpu_change_row.set_title("CPU Change Threshold")
        cpu_change_row.set_subtitle("Show processes when CPU usage changes by this percentage")
        cpu_change_row.set_value(self.settings.get("cpu_change_threshold"))
        cpu_change_row.connect("notify::value", self._on_cpu_change_threshold_changed)
        change_group.add(cpu_change_row)
        
        # Memory change threshold
        mem_change_row = Adw.SpinRow.new_with_range(1, 50, 1)
        mem_change_row.set_title("Memory Change Threshold")
        mem_change_row.set_subtitle("Show processes when memory usage changes by this percentage")
        mem_change_row.set_value(self.settings.get("memory_change_threshold"))
        mem_change_row.connect("notify::value", self._on_mem_change_threshold_changed)
        change_group.add(mem_change_row)
        
        # Warning thresholds group (for future row highlighting feature)
        warning_group = Adw.PreferencesGroup()
        warning_group.set_title("Warning Thresholds")
        warning_group.set_description("Thresholds for highlighting high resource usage (planned feature)")
        thresholds_page.add(warning_group)
        
        # CPU threshold
        cpu_row = Adw.SpinRow.new_with_range(10, 100, 5)
        cpu_row.set_title("CPU Warning Threshold")
        cpu_row.set_subtitle("Highlight processes using more than this CPU percentage")
        cpu_row.set_value(self.settings.get("cpu_threshold_warning"))
        cpu_row.connect("notify::value", self._on_cpu_threshold_changed)
        warning_group.add(cpu_row)
        
        # Memory threshold
        mem_row = Adw.SpinRow.new_with_range(10, 100, 5)
        mem_row.set_title("Memory Warning Threshold")
        mem_row.set_subtitle("Highlight processes using more than this memory percentage")
        mem_row.set_value(self.settings.get("memory_threshold_warning"))
        mem_row.connect("notify::value", self._on_mem_threshold_changed)
        warning_group.add(mem_row)
    
    def _on_refresh_changed(self, row: Adw.SpinRow, param: Any) -> None:
        """Handle refresh interval change."""
        self.settings.set("refresh_interval", int(row.get_value()))
    
    def _on_confirm_changed(self, row: Adw.SwitchRow, param: Any) -> None:
        """Handle confirm kill change."""
        self.settings.set("confirm_kill", row.get_active())
    
    def _on_kernel_changed(self, row: Adw.SwitchRow, param: Any) -> None:
        """Handle show kernel threads change."""
        self.settings.set("show_kernel_threads", row.get_active())
    
    def _on_theme_changed(self, row: Adw.ComboRow, param: Any) -> None:
        """Handle theme change and apply immediately."""
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
    
    def _on_cpu_change_threshold_changed(self, row: Adw.SpinRow, param: Any) -> None:
        """Handle CPU change threshold change."""
        self.settings.set("cpu_change_threshold", int(row.get_value()))
    
    def _on_mem_change_threshold_changed(self, row: Adw.SpinRow, param: Any) -> None:
        """Handle memory change threshold change."""
        self.settings.set("memory_change_threshold", int(row.get_value()))
    
    def _on_cpu_threshold_changed(self, row: Adw.SpinRow, param: Any) -> None:
        """Handle CPU threshold change."""
        self.settings.set("cpu_threshold_warning", int(row.get_value()))
    
    def _on_mem_threshold_changed(self, row: Adw.SpinRow, param: Any) -> None:
        """Handle memory threshold change."""
        self.settings.set("memory_threshold_warning", int(row.get_value()))
    
    def _on_reset_clicked(self, button: Gtk.Button) -> None:
        """Handle reset to defaults button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Reset Settings?",
            body="This will restore all settings to their default values."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_reset_response)
        dialog.present()
    
    def _on_reset_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        """Handle reset confirmation response."""
        if response == "reset":
            self.settings.reset()
            self.close()
    
    def _build_alerts_page(self) -> None:
        """Build the Alerts preferences page."""
        alerts_page = Adw.PreferencesPage()
        alerts_page.set_title("Alerts")
        alerts_page.set_icon_name("dialog-information-symbolic")
        self.add(alerts_page)
        
        # Alerts settings group
        settings_group = Adw.PreferencesGroup()
        settings_group.set_title("Alert Settings")
        settings_group.set_description("Configure how process alerts work")
        alerts_page.add(settings_group)
        
        # Enable alerts
        self.alerts_enabled_row = Adw.SwitchRow()
        self.alerts_enabled_row.set_title("Enable Alerts")
        self.alerts_enabled_row.set_subtitle("Monitor processes for high resource usage")
        self.alerts_enabled_row.set_active(self.settings.get("alerts_enabled", False))
        self.alerts_enabled_row.connect("notify::active", self._on_alerts_enabled_changed)
        settings_group.add(self.alerts_enabled_row)
        
        # Desktop notifications
        notifications_row = Adw.SwitchRow()
        notifications_row.set_title("Desktop Notifications")
        notifications_row.set_subtitle("Show desktop notifications when alerts are triggered")
        notifications_row.set_active(self.settings.get("alert_notifications", True))
        notifications_row.connect("notify::active", self._on_notifications_changed)
        settings_group.add(notifications_row)
        
        # Alert rules group
        self.rules_group = Adw.PreferencesGroup()
        self.rules_group.set_title("Alert Rules")
        self.rules_group.set_description("Define rules for process monitoring")
        alerts_page.add(self.rules_group)
        
        # Add rule button
        add_rule_row = Adw.ActionRow()
        add_rule_row.set_title("Add New Rule")
        add_rule_row.set_subtitle("Create a new alert rule for CPU or memory usage")
        
        add_button = Gtk.Button()
        add_button.set_icon_name("list-add-symbolic")
        add_button.set_valign(Gtk.Align.CENTER)
        add_button.add_css_class("flat")
        add_button.connect("clicked", self._on_add_rule_clicked)
        add_rule_row.add_suffix(add_button)
        add_rule_row.set_activatable_widget(add_button)
        self.rules_group.add(add_rule_row)
        
        # Load existing rules
        self._load_alert_rules()
    
    def _load_alert_rules(self) -> None:
        """Load and display existing alert rules."""
        rules = self.settings.get("alert_rules", [])
        for rule in rules:
            self._add_rule_row(rule)
    
    def _add_rule_row(self, rule: Dict[str, Any]) -> None:
        """Add a row for an alert rule.
        
        Args:
            rule: Alert rule dictionary with id, type, threshold, enabled.
        """
        rule_id = rule.get('id', str(uuid.uuid4()))
        rule_type = rule.get('type', 'cpu')
        threshold = rule.get('threshold', 80)
        enabled = rule.get('enabled', True)
        
        row = Adw.ActionRow()
        
        # Set title based on type
        type_label = "CPU" if rule_type == "cpu" else "Memory"
        row.set_title(f"{type_label} > {threshold}%")
        row.set_subtitle(f"Alert when {type_label.lower()} usage exceeds {threshold}%")
        
        # Enable/disable toggle
        toggle = Gtk.Switch()
        toggle.set_active(enabled)
        toggle.set_valign(Gtk.Align.CENTER)
        toggle.connect("notify::active", lambda w, p: self._on_rule_toggle_changed(rule_id, w.get_active()))
        row.add_prefix(toggle)
        
        # Edit button
        edit_button = Gtk.Button()
        edit_button.set_icon_name("document-edit-symbolic")
        edit_button.set_valign(Gtk.Align.CENTER)
        edit_button.add_css_class("flat")
        edit_button.set_tooltip_text("Edit rule")
        edit_button.connect("clicked", lambda b: self._on_edit_rule_clicked(rule_id))
        row.add_suffix(edit_button)
        
        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.add_css_class("flat")
        delete_button.set_tooltip_text("Delete rule")
        delete_button.connect("clicked", lambda b: self._on_delete_rule_clicked(rule_id))
        row.add_suffix(delete_button)
        
        self.rules_group.add(row)
        self._alert_rows[rule_id] = row
    
    def _on_alerts_enabled_changed(self, row: Adw.SwitchRow, param: Any) -> None:
        """Handle alerts enabled change."""
        self.settings.set("alerts_enabled", row.get_active())
    
    def _on_notifications_changed(self, row: Adw.SwitchRow, param: Any) -> None:
        """Handle notifications enabled change."""
        self.settings.set("alert_notifications", row.get_active())
    
    def _on_rule_toggle_changed(self, rule_id: str, enabled: bool) -> None:
        """Handle rule enable/disable toggle."""
        rules = self.settings.get("alert_rules", [])
        for rule in rules:
            if rule.get('id') == rule_id:
                rule['enabled'] = enabled
                break
        self.settings.set("alert_rules", rules)
    
    def _on_add_rule_clicked(self, button: Gtk.Button) -> None:
        """Handle add rule button click."""
        self._show_rule_dialog(None)
    
    def _on_edit_rule_clicked(self, rule_id: str) -> None:
        """Handle edit rule button click."""
        rules = self.settings.get("alert_rules", [])
        rule = next((r for r in rules if r.get('id') == rule_id), None)
        if rule:
            self._show_rule_dialog(rule)
    
    def _on_delete_rule_clicked(self, rule_id: str) -> None:
        """Handle delete rule button click."""
        # Remove from settings
        rules = self.settings.get("alert_rules", [])
        rules = [r for r in rules if r.get('id') != rule_id]
        self.settings.set("alert_rules", rules)
        
        # Remove row from UI
        if rule_id in self._alert_rows:
            row = self._alert_rows[rule_id]
            self.rules_group.remove(row)
            del self._alert_rows[rule_id]
    
    def _show_rule_dialog(self, rule: Optional[Dict[str, Any]]) -> None:
        """Show dialog to add or edit an alert rule.
        
        Args:
            rule: Existing rule to edit, or None to create a new rule.
        """
        is_new = rule is None
        rule_id = rule.get('id', str(uuid.uuid4())) if rule else str(uuid.uuid4())
        current_type = rule.get('type', 'cpu') if rule else 'cpu'
        current_threshold = rule.get('threshold', 80) if rule else 80
        
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Add Alert Rule" if is_new else "Edit Alert Rule",
            body="Set the type and threshold for this alert rule."
        )
        
        # Create content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        
        # Type selection
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        type_label = Gtk.Label(label="Type:")
        type_label.set_width_chars(10)
        type_label.set_xalign(0)
        type_box.append(type_label)
        
        type_dropdown = Gtk.DropDown()
        type_model = Gtk.StringList()
        type_model.append("CPU")
        type_model.append("Memory")
        type_dropdown.set_model(type_model)
        type_dropdown.set_selected(0 if current_type == 'cpu' else 1)
        type_dropdown.set_hexpand(True)
        type_box.append(type_dropdown)
        content_box.append(type_box)
        
        # Threshold input
        threshold_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        threshold_label = Gtk.Label(label="Threshold:")
        threshold_label.set_width_chars(10)
        threshold_label.set_xalign(0)
        threshold_box.append(threshold_label)
        
        threshold_spin = Gtk.SpinButton()
        threshold_spin.set_range(1, 100)
        threshold_spin.set_increments(5, 10)
        threshold_spin.set_value(current_threshold)
        threshold_spin.set_hexpand(True)
        threshold_box.append(threshold_spin)
        
        percent_label = Gtk.Label(label="%")
        threshold_box.append(percent_label)
        content_box.append(threshold_box)
        
        dialog.set_extra_child(content_box)
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        
        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "save":
                rule_type = 'cpu' if type_dropdown.get_selected() == 0 else 'memory'
                threshold = int(threshold_spin.get_value())
                
                new_rule = {
                    'id': rule_id,
                    'type': rule_type,
                    'threshold': threshold,
                    'enabled': True
                }
                
                rules = self.settings.get("alert_rules", [])
                
                if is_new:
                    # Add new rule
                    rules.append(new_rule)
                    self.settings.set("alert_rules", rules)
                    self._add_rule_row(new_rule)
                else:
                    # Update existing rule
                    for i, r in enumerate(rules):
                        if r.get('id') == rule_id:
                            rules[i] = new_rule
                            break
                    self.settings.set("alert_rules", rules)
                    
                    # Update row UI
                    if rule_id in self._alert_rows:
                        row = self._alert_rows[rule_id]
                        type_label_str = "CPU" if rule_type == "cpu" else "Memory"
                        row.set_title(f"{type_label_str} > {threshold}%")
                        row.set_subtitle(f"Alert when {type_label_str.lower()} usage exceeds {threshold}%")
        
        dialog.connect("response", on_response)
        dialog.present()

