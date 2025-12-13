# SPDX-License-Identifier: GPL-3.0-or-later
# Stats bar mixin for ProcessManagerWindow

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import math
from gi.repository import Gtk


class StatsBarMixin:
    """Mixin class providing stats bar functionality for ProcessManagerWindow.
    
    This mixin expects the following attributes on self:
    - system_stats: SystemStats instance
    - gpu_stats: GPUStats instance
    - current_tab: str
    - format_memory: method
    """
    
    # Initialize percent values
    cpu_percent = 0
    mem_percent = 0
    swap_percent = 0
    disk_percent = 0
    gpu_percent = 0
    gpu_encoding_percent = 0
    gpu_decoding_percent = 0
    
    def create_stats_bar(self):
        """Create the system stats bar at the bottom."""
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        stats_box.set_margin_start(12)
        stats_box.set_margin_end(12)
        stats_box.set_margin_top(8)
        stats_box.set_margin_bottom(8)
        stats_box.add_css_class("stats-bar")
        
        # CPU section
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.cpu_indicator = Gtk.DrawingArea()
        self.cpu_indicator.set_size_request(24, 24)
        self.cpu_indicator.set_draw_func(self.draw_cpu_indicator)
        cpu_box.append(self.cpu_indicator)
        
        cpu_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.cpu_title = Gtk.Label(label="CPU")
        self.cpu_title.add_css_class("heading")
        self.cpu_title.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_title)
        
        self.cpu_details = Gtk.Label(label="0%")
        self.cpu_details.add_css_class("dim-label")
        self.cpu_details.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_details)
        
        self.cpu_load = Gtk.Label(label="Load: 0.00")
        self.cpu_load.add_css_class("dim-label")
        self.cpu_load.set_halign(Gtk.Align.START)
        cpu_label_box.append(self.cpu_load)
        
        cpu_box.append(cpu_label_box)
        stats_box.append(cpu_box)
        
        # Separator
        sep_cpu = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep_cpu)
        
        # Memory section
        mem_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.mem_indicator = Gtk.DrawingArea()
        self.mem_indicator.set_size_request(24, 24)
        self.mem_indicator.set_draw_func(self.draw_memory_indicator)
        mem_box.append(self.mem_indicator)
        
        mem_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.mem_title = Gtk.Label(label="Memory")
        self.mem_title.add_css_class("heading")
        self.mem_title.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_title)
        
        self.mem_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.mem_details.add_css_class("dim-label")
        self.mem_details.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_details)
        
        self.mem_cache = Gtk.Label(label="Cache 0 B")
        self.mem_cache.add_css_class("dim-label")
        self.mem_cache.set_halign(Gtk.Align.START)
        mem_label_box.append(self.mem_cache)
        
        mem_box.append(mem_label_box)
        stats_box.append(mem_box)
        
        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep)
        
        # Swap section
        swap_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.swap_indicator = Gtk.DrawingArea()
        self.swap_indicator.set_size_request(24, 24)
        self.swap_indicator.set_draw_func(self.draw_swap_indicator)
        swap_box.append(self.swap_indicator)
        
        swap_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.swap_title = Gtk.Label(label="Swap")
        self.swap_title.add_css_class("heading")
        self.swap_title.set_halign(Gtk.Align.START)
        swap_label_box.append(self.swap_title)
        
        self.swap_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.swap_details.add_css_class("dim-label")
        self.swap_details.set_halign(Gtk.Align.START)
        swap_label_box.append(self.swap_details)
        
        swap_box.append(swap_label_box)
        stats_box.append(swap_box)
        
        # GPU stats section (shown when on GPU tab)
        gpu_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(gpu_sep)
        
        gpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.gpu_indicator = Gtk.DrawingArea()
        self.gpu_indicator.set_size_request(24, 24)
        self.gpu_indicator.set_draw_func(self.draw_gpu_indicator)
        gpu_box.append(self.gpu_indicator)
        
        gpu_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.gpu_title = Gtk.Label(label="GPU")
        self.gpu_title.add_css_class("heading")
        self.gpu_title.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_title)
        
        self.gpu_details = Gtk.Label(label="0%")
        self.gpu_details.add_css_class("dim-label")
        self.gpu_details.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_details)
        
        self.gpu_enc_dec = Gtk.Label(label="Enc: 0% | Dec: 0%")
        self.gpu_enc_dec.add_css_class("dim-label")
        self.gpu_enc_dec.set_halign(Gtk.Align.START)
        gpu_label_box.append(self.gpu_enc_dec)
        
        gpu_box.append(gpu_label_box)
        stats_box.append(gpu_box)
        self.gpu_stats_section = gpu_box
        self.gpu_stats_sep = gpu_sep
        
        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        stats_box.append(sep2)
        
        # Disk section
        disk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.disk_indicator = Gtk.DrawingArea()
        self.disk_indicator.set_size_request(24, 24)
        self.disk_indicator.set_draw_func(self.draw_disk_indicator)
        disk_box.append(self.disk_indicator)
        
        disk_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        self.disk_title = Gtk.Label(label="Disk")
        self.disk_title.add_css_class("heading")
        self.disk_title.set_halign(Gtk.Align.START)
        disk_label_box.append(self.disk_title)
        
        self.disk_details = Gtk.Label(label="0 B (0%) of 0 B")
        self.disk_details.add_css_class("dim-label")
        self.disk_details.set_halign(Gtk.Align.START)
        disk_label_box.append(self.disk_details)
        
        disk_box.append(disk_label_box)
        stats_box.append(disk_box)
        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        stats_box.append(spacer)
        
        # Initially hide GPU stats
        self.gpu_stats_section.set_visible(False)
        self.gpu_stats_sep.set_visible(False)
        
        return stats_box
    
    def draw_cpu_indicator(self, area, cr, width, height):
        """Draw circular CPU usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.cpu_percent, (0.2, 0.6, 0.8))
    
    def draw_memory_indicator(self, area, cr, width, height):
        """Draw circular memory usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.mem_percent, (0.8, 0.2, 0.2))
    
    def draw_swap_indicator(self, area, cr, width, height):
        """Draw circular swap usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.swap_percent, (0.2, 0.8, 0.2))
    
    def draw_disk_indicator(self, area, cr, width, height):
        """Draw circular disk usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.disk_percent, (0.2, 0.2, 0.8))
    
    def draw_gpu_indicator(self, area, cr, width, height):
        """Draw circular GPU usage indicator."""
        self.draw_circular_indicator(cr, width, height, self.gpu_percent, (0.8, 0.5, 0.2))
    
    def draw_circular_indicator(self, cr, width, height, percent, color):
        """Draw a circular progress indicator."""
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 2
        line_width = 3
        
        # Background circle
        cr.set_line_width(line_width)
        cr.set_source_rgba(0.3, 0.3, 0.3, 0.5)
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()
        
        # Progress arc
        if percent > 0:
            cr.set_source_rgba(*color, 1.0)
            start_angle = -math.pi / 2
            end_angle = start_angle + (2 * math.pi * percent / 100)
            cr.arc(center_x, center_y, radius, start_angle, end_angle)
            cr.stroke()
    
    def update_system_stats(self):
        """Update system CPU, memory, swap, disk, and GPU stats."""
        # CPU
        cpu_stats = self.system_stats.get_cpu_usage()
        self.cpu_percent = cpu_stats.get('cpu_usage', 0)
        self.cpu_details.set_text(f"{self.cpu_percent:.1f}%")
        
        # Load average
        load_avg = self.system_stats.get_load_average()
        self.cpu_load.set_text(f"Load: {load_avg['1min']:.2f}")
        self.cpu_indicator.queue_draw()
        
        # Memory
        stats = self.system_stats.get_memory_info()
        mem_used = stats['mem_used']
        mem_total = stats['mem_total']
        mem_cache = stats['mem_cache']
        self.mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
        
        self.mem_details.set_text(
            f"{self.format_memory(mem_used)} ({self.mem_percent:.1f}%) of {self.format_memory(mem_total)}"
        )
        self.mem_cache.set_text(f"Cache {self.format_memory(mem_cache)}")
        self.mem_indicator.queue_draw()
        
        # Swap
        swap_used = stats['swap_used']
        swap_total = stats['swap_total']
        self.swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0
        
        self.swap_details.set_text(
            f"{self.format_memory(swap_used)} ({self.swap_percent:.1f}%) of {self.format_memory(swap_total)}"
        )
        self.swap_indicator.queue_draw()
        
        # GPU stats (only update when on GPU tab)
        if self.current_tab == 'gpu':
            gpu_stats = self.gpu_stats.get_total_gpu_stats()
            self.gpu_percent = gpu_stats.get('total_gpu_usage', 0)
            self.gpu_encoding_percent = gpu_stats.get('total_encoding', 0)
            self.gpu_decoding_percent = gpu_stats.get('total_decoding', 0)
            
            self.gpu_details.set_text(f"{self.gpu_percent:.1f}%")
            self.gpu_enc_dec.set_text(
                f"Enc: {self.gpu_encoding_percent:.1f}% | Dec: {self.gpu_decoding_percent:.1f}%"
            )
            self.gpu_indicator.queue_draw()
            
            # Show GPU stats section
            self.gpu_stats_section.set_visible(True)
            self.gpu_stats_sep.set_visible(True)
        else:
            # Hide GPU stats section when not on GPU tab
            self.gpu_stats_section.set_visible(False)
            self.gpu_stats_sep.set_visible(False)
        
        # Disk
        disk_stats = self.system_stats.get_disk_info()
        disk_used = disk_stats['disk_used']
        disk_total = disk_stats['disk_total']
        self.disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
        
        self.disk_details.set_text(
            f"{self.format_memory(disk_used)} ({self.disk_percent:.1f}%) of {self.format_memory(disk_total)}"
        )
        self.disk_indicator.queue_draw()
