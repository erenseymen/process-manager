# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics facade

"""GPU statistics and monitoring for Intel, NVIDIA, and AMD GPUs.

This module provides a unified interface for GPU monitoring across
different GPU vendors. It uses background threading for non-blocking
data collection.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Callable

from .detector import detect_gpus
from .base import GPUProvider

if TYPE_CHECKING:
    pass

# Re-export GPUStats as the main class
__all__ = ['GPUStats']


class GPUStats:
    """GPU statistics and monitoring for Intel, NVIDIA, and AMD GPUs.
    
    Uses background threading for non-blocking GPU data collection and
    parallel execution for multiple GPU types.
    """
    
    def __init__(self) -> None:
        # Detect available GPUs
        self.gpu_types: List[str] = detect_gpus()
        
        # Initialize providers for detected GPUs
        self._providers: Dict[str, GPUProvider] = {}
        self._init_providers()
        
        # Cached GPU data (updated by background thread)
        self._gpu_processes_cache: Dict[int, Dict[str, Any]] = {}
        self._gpu_total_stats_cache: Dict[str, Any] = {
            'total_gpu_usage': 0.0,
            'total_encoding': 0.0,
            'total_decoding': 0.0,
            'gpu_types': []
        }
        self._cache_lock = threading.Lock()
        self._cache_time: float = 0.0
        self._cache_ttl: float = 1.8  # 1.8 seconds (slightly less than 2s refresh)
        
        # Background update thread control
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._update_callback: Optional[Callable[[], None]] = None
    
    def _init_providers(self) -> None:
        """Initialize GPU providers based on detected GPU types."""
        if 'nvidia' in self.gpu_types:
            from .nvidia import NvidiaProvider
            self._providers['nvidia'] = NvidiaProvider()
        
        if 'intel' in self.gpu_types:
            from .intel import IntelProvider
            self._providers['intel'] = IntelProvider()
        
        if 'amd' in self.gpu_types:
            from .amd import AMDProvider
            self._providers['amd'] = AMDProvider()
    
    def start_background_updates(self, callback: Optional[Callable[[], None]] = None) -> None:
        """Start background thread for GPU data updates.
        
        Args:
            callback: Optional callback function to invoke when data is updated.
                     This should be a GLib.idle_add wrapper for UI updates.
        """
        if self._update_thread is not None and self._update_thread.is_alive():
            return  # Already running
        
        self._update_callback = callback
        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._background_update_loop,
            daemon=True,
            name="GPUStatsUpdater"
        )
        self._update_thread.start()
    
    def stop_background_updates(self) -> None:
        """Stop the background update thread."""
        self._stop_event.set()
        if self._update_thread is not None and self._update_thread.is_alive():
            self._update_thread.join(timeout=5.0)
            if not self._update_thread.is_alive():
                self._update_thread = None
        else:
            self._update_thread = None
    
    def _background_update_loop(self) -> None:
        """Background thread loop that periodically updates GPU data."""
        while not self._stop_event.is_set():
            try:
                self._update_gpu_data()
                if self._update_callback:
                    self._update_callback()
            except Exception:
                pass  # Silently ignore errors in background thread
            
            self._stop_event.wait(timeout=self._cache_ttl)
    
    def _update_gpu_data(self) -> None:
        """Update GPU data in background thread using parallel execution."""
        processes: Dict[int, Dict[str, Any]] = {}
        total_stats = {
            'total_gpu_usage': 0.0,
            'total_encoding': 0.0,
            'total_decoding': 0.0,
            'gpu_types': self.gpu_types.copy()
        }
        
        if not self._providers:
            with self._cache_lock:
                self._gpu_processes_cache = processes
                self._gpu_total_stats_cache = total_stats
                self._cache_time = time.time()
            return
        
        # Run GPU queries in parallel for each provider
        with ThreadPoolExecutor(max_workers=len(self._providers)) as executor:
            futures = {}
            
            for name, provider in self._providers.items():
                futures[f'{name}_procs'] = executor.submit(provider.get_processes)
                futures[f'{name}_stats'] = executor.submit(provider.get_total_stats)
            
            # Collect results
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=5)
                except Exception:
                    results[name] = {} if 'procs' in name else {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        # Merge process data from all providers
        for vendor in self._providers.keys():
            procs_key = f'{vendor}_procs'
            if procs_key in results:
                for pid, info in results[procs_key].items():
                    if pid not in processes:
                        processes[pid] = {}
                    
                    # Merge GPU usage
                    current_usage = processes[pid].get('gpu_usage', 0)
                    new_usage = info.get('gpu_usage', 0)
                    processes[pid]['gpu_usage'] = current_usage + new_usage
                    
                    # Merge other stats
                    processes[pid]['gpu_memory'] = processes[pid].get('gpu_memory', 0) + info.get('gpu_memory', 0)
                    processes[pid]['encoding'] = processes[pid].get('encoding', 0) + info.get('encoding', 0)
                    processes[pid]['decoding'] = processes[pid].get('decoding', 0) + info.get('decoding', 0)
                    processes[pid]['gpu_type'] = vendor
        
        # Merge total stats (take max across vendors)
        for vendor in self._providers.keys():
            stats_key = f'{vendor}_stats'
            if stats_key in results:
                stats = results[stats_key]
                total_stats['total_gpu_usage'] = max(total_stats['total_gpu_usage'], stats.get('gpu_usage', 0))
                total_stats['total_encoding'] = max(total_stats['total_encoding'], stats.get('encoding', 0))
                total_stats['total_decoding'] = max(total_stats['total_decoding'], stats.get('decoding', 0))
        
        # Update cache with lock
        with self._cache_lock:
            self._gpu_processes_cache = processes
            self._gpu_total_stats_cache = total_stats
            self._cache_time = time.time()
    
    def get_gpu_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get GPU usage per process from cache.
        
        Returns cached data from background thread. If cache is empty or stale,
        triggers a synchronous update (fallback for first call).
        
        Returns:
            Dictionary mapping PID to GPU usage info.
        """
        with self._cache_lock:
            if self._cache_time > 0 and (time.time() - self._cache_time) < self._cache_ttl * 2:
                return self._gpu_processes_cache.copy()
        
        # Fallback: synchronous update if no cached data
        self._update_gpu_data()
        with self._cache_lock:
            return self._gpu_processes_cache.copy()
    
    def get_total_gpu_stats(self) -> Dict[str, Any]:
        """Get total GPU usage statistics from cache.
        
        Returns cached data from background thread.
        
        Returns:
            Dictionary with total GPU stats.
        """
        with self._cache_lock:
            if self._cache_time > 0 and (time.time() - self._cache_time) < self._cache_ttl * 2:
                return self._gpu_total_stats_cache.copy()
        
        # Fallback: synchronous update if no cached data
        self._update_gpu_data()
        with self._cache_lock:
            return self._gpu_total_stats_cache.copy()
