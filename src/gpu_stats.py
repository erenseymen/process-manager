# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Callable

from .ps_commands import run_host_command, is_flatpak

if TYPE_CHECKING:
    pass


class GPUStats:
    """GPU statistics and monitoring for Intel, NVIDIA, and AMD GPUs.
    
    Uses background threading for non-blocking GPU data collection and
    parallel execution for multiple GPU types.
    """
    
    def __init__(self) -> None:
        self.gpu_types: List[str] = []
        self._detect_gpus()
        
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
        
        # Per-GPU type caches for internal use
        self._intel_cache: Optional[Dict[str, Any]] = None
        self._intel_cache_time: float = 0.0
    
    def _detect_gpus(self) -> None:
        """Detect available GPU types."""
        self.gpu_types = []
        
        # Check for NVIDIA GPU
        try:
            # Try via host command first (for Flatpak)
            cmd = ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                self.gpu_types.append('nvidia')
            else:
                # Try via flatpak-spawn if direct call failed
                result = run_host_command(cmd)
                if result.strip():
                    self.gpu_types.append('nvidia')
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # Try via flatpak-spawn as fallback
            try:
                result = run_host_command(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])
                if result.strip():
                    self.gpu_types.append('nvidia')
            except Exception:
                pass
        
        # Check for Intel GPU
        # First, check /sys/class/drm for Intel vendor ID (most reliable method)
        intel_detected = False
        try:
            for i in range(10):
                vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                if os.path.exists(vendor_path):
                    try:
                        with open(vendor_path, 'r') as f:
                            vendor_id = f.read().strip()
                            if vendor_id == '0x8086':
                                self.gpu_types.append('intel')
                                intel_detected = True
                                break
                    except (OSError, IOError):
                        pass
        except Exception:
            pass
        
        # If not detected via vendor ID, try intel_gpu_top command
        if not intel_detected:
            try:
                # Try direct call first
                result = subprocess.run(
                    ['intel_gpu_top', '-l'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    self.gpu_types.append('intel')
                    intel_detected = True
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                # Try via flatpak-spawn
                try:
                    result = run_host_command(['intel_gpu_top', '-l'])
                    # If command exists (even if empty output), it means intel_gpu_top is available
                    # This suggests Intel GPU might be present
                    if result is not None:  # Command executed (even if empty)
                        # Double-check via vendor ID if we haven't already
                        if not intel_detected:
                            for i in range(10):
                                vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                                if os.path.exists(vendor_path):
                                    try:
                                        with open(vendor_path, 'r') as f:
                                            vendor_id = f.read().strip()
                                            if vendor_id == '0x8086':
                                                self.gpu_types.append('intel')
                                                intel_detected = True
                                                break
                                    except (OSError, IOError):
                                        pass
                except Exception:
                    pass
        
        # Check for AMD GPU
        try:
            # Try direct call first
            result = subprocess.run(
                ['radeontop', '-l', '1', '-d', '-'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self.gpu_types.append('amd')
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # Try via flatpak-spawn
            try:
                run_host_command(['radeontop', '-l', '1', '-d', '-'])
                # If command exists, verify by checking /sys/class/drm
                for i in range(10):
                    vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                    if os.path.exists(vendor_path):
                        try:
                            with open(vendor_path, 'r') as f:
                                vendor_id = f.read().strip()
                                # AMD vendor IDs: 0x1002 (AMD), 0x1022 (AMD/ATI)
                                if vendor_id in ['0x1002', '0x1022']:
                                    self.gpu_types.append('amd')
                                    break
                        except (OSError, IOError):
                            pass
            except Exception:
                # Also check /sys/class/drm for AMD GPU (fallback)
                try:
                    for i in range(10):
                        vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                        if os.path.exists(vendor_path):
                            try:
                                with open(vendor_path, 'r') as f:
                                    vendor_id = f.read().strip()
                                    # AMD vendor IDs: 0x1002 (AMD), 0x1022 (AMD/ATI)
                                    if vendor_id in ['0x1002', '0x1022']:
                                        self.gpu_types.append('amd')
                                        break
                            except (OSError, IOError):
                                pass
                except Exception:
                    pass
    
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
        if self._update_thread is not None:
            self._update_thread.join(timeout=2.0)
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
            
            # Wait for next update cycle or stop signal
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
        
        if not self.gpu_types:
            with self._cache_lock:
                self._gpu_processes_cache = processes
                self._gpu_total_stats_cache = total_stats
                self._cache_time = time.time()
            return
        
        # Run GPU queries in parallel for each GPU type
        with ThreadPoolExecutor(max_workers=len(self.gpu_types)) as executor:
            futures = {}
            
            if 'nvidia' in self.gpu_types:
                futures['nvidia_procs'] = executor.submit(self._get_nvidia_processes)
                futures['nvidia_stats'] = executor.submit(self._get_nvidia_total_stats)
            
            if 'intel' in self.gpu_types:
                futures['intel_procs'] = executor.submit(self._get_intel_processes)
                futures['intel_stats'] = executor.submit(self._get_intel_total_stats)
            
            if 'amd' in self.gpu_types:
                futures['amd_procs'] = executor.submit(self._get_amd_processes)
                futures['amd_stats'] = executor.submit(self._get_amd_total_stats)
            
            # Collect results
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=5)
                except Exception:
                    results[name] = {} if 'procs' in name else {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        # Merge process data
        if 'nvidia_procs' in results:
            for pid, info in results['nvidia_procs'].items():
                if pid not in processes:
                    processes[pid] = {}
                processes[pid].update(info)
                processes[pid]['gpu_type'] = 'nvidia'
        
        if 'intel_procs' in results:
            for pid, info in results['intel_procs'].items():
                if pid not in processes:
                    processes[pid] = {}
                if 'gpu_usage' in processes[pid]:
                    processes[pid]['gpu_usage'] = processes[pid].get('gpu_usage', 0) + info.get('gpu_usage', 0)
                else:
                    processes[pid]['gpu_usage'] = info.get('gpu_usage', 0)
                processes[pid]['encoding'] = processes[pid].get('encoding', 0) + info.get('encoding', 0)
                processes[pid]['decoding'] = processes[pid].get('decoding', 0) + info.get('decoding', 0)
                processes[pid]['gpu_type'] = 'intel'
        
        if 'amd_procs' in results:
            for pid, info in results['amd_procs'].items():
                if pid not in processes:
                    processes[pid] = {}
                if 'gpu_usage' in processes[pid]:
                    processes[pid]['gpu_usage'] = processes[pid].get('gpu_usage', 0) + info.get('gpu_usage', 0)
                else:
                    processes[pid]['gpu_usage'] = info.get('gpu_usage', 0)
                processes[pid]['gpu_type'] = 'amd'
        
        # Merge total stats
        for gpu_type in ['nvidia', 'intel', 'amd']:
            stats_key = f'{gpu_type}_stats'
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
            # If cache is valid, return it
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
            # If cache is valid, return it
            if self._cache_time > 0 and (time.time() - self._cache_time) < self._cache_ttl * 2:
                return self._gpu_total_stats_cache.copy()
        
        # Fallback: synchronous update if no cached data
        self._update_gpu_data()
        with self._cache_lock:
            return self._gpu_total_stats_cache.copy()
    
    def _get_nvidia_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get NVIDIA GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Use nvidia-smi to get process info with GPU utilization
            # First get processes with memory usage
            cmd = [
                'nvidia-smi',
                '--query-compute-apps=pid,used_memory,process_name',
                '--format=csv,noheader,nounits'
            ]
            output = run_host_command(cmd)
            
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        memory_mb = int(parts[1]) if parts[1] else 0
                        processes[pid] = {
                            'gpu_usage': 0.0,
                            'gpu_memory': memory_mb * 1024 * 1024,
                            'encoding': 0.0,
                            'decoding': 0.0
                        }
                    except (ValueError, IndexError):
                        continue
            
            # Get per-process GPU utilization using pmon or process info
            try:
                # Try to get GPU utilization per process
                cmd = [
                    'nvidia-smi',
                    '--query-compute-apps=pid,sm,memory',
                    '--format=csv,noheader,nounits'
                ]
                output = run_host_command(cmd)
                for line in output.strip().split('\n'):
                    if not line.strip():
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[0])
                            sm_usage = float(parts[1]) if parts[1] else 0.0
                            if pid in processes:
                                # SM (Streaming Multiprocessor) usage is a good indicator
                                processes[pid]['gpu_usage'] = sm_usage
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
            
            # Try to get encoding/decoding info
            try:
                cmd = [
                    'nvidia-smi',
                    '--query-encoder-sessions=pid,codec_type,codec_name,session_id',
                    '--format=csv,noheader'
                ]
                output = run_host_command(cmd)
                for line in output.strip().split('\n'):
                    if not line.strip():
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0])
                            codec_type = parts[1].lower()
                            if pid in processes:
                                if 'encode' in codec_type or 'h264' in codec_type or 'hevc' in codec_type:
                                    processes[pid]['encoding'] = 30.0  # Estimate based on active session
                                elif 'decode' in codec_type:
                                    processes[pid]['decoding'] = 30.0  # Estimate based on active session
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
                
        except Exception:
            pass
        
        return processes
    
    def _parse_intel_gpu_top_json(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse intel_gpu_top JSON output, handling incomplete arrays.
        
        intel_gpu_top outputs a continuous JSON array. When killed mid-output,
        the array may be incomplete. This method tries to extract the last
        complete JSON object from the output.
        
        Args:
            output: Raw JSON output from intel_gpu_top
            
        Returns:
            The last complete reading dict, or None if parsing fails
        """
        if not output or not output.strip():
            return None
        
        output = output.strip()
        
        # First, try to parse as complete JSON
        try:
            data = json.loads(output)
            if isinstance(data, list) and len(data) > 0:
                return data[-1]
            elif isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        
        # If that fails, try to find and extract the last complete object
        # The format is: [ {obj1}, {obj2}, ...
        # Find the last complete object by looking for },\n{ or }] patterns
        try:
            # Find the last complete "}" that closes an object
            # Objects are separated by },\n{
            last_complete_end = -1
            brace_count = 0
            in_string = False
            escape_next = False
            
            for i, char in enumerate(output):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                    
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_complete_end = i
            
            if last_complete_end > 0:
                # Find the start of this object
                # Look backwards from last_complete_end to find the matching {
                obj_start = -1
                brace_count = 0
                for i in range(last_complete_end, -1, -1):
                    char = output[i]
                    if char == '}':
                        brace_count += 1
                    elif char == '{':
                        brace_count -= 1
                        if brace_count == 0:
                            obj_start = i
                            break
                
                if obj_start >= 0:
                    obj_str = output[obj_start:last_complete_end + 1]
                    return json.loads(obj_str)
        except (json.JSONDecodeError, IndexError, ValueError):
            pass
        
        return None

    def _get_intel_gpu_data_cached(self) -> Optional[Dict[str, Any]]:
        """Get Intel GPU data with caching to avoid multiple slow calls per refresh cycle."""
        now = time.time()
        
        # Return cached data if still valid
        if self._intel_cache is not None and (now - self._intel_cache_time) < self._cache_ttl:
            return self._intel_cache
        
        # Fetch fresh data
        cmd_json = ['sudo', '-n', 'timeout', '1', 'intel_gpu_top', '-J', '-o', '-']
        try:
            output_json = run_host_command(cmd_json, timeout=3)
            
            if output_json and output_json.strip():
                data = self._parse_intel_gpu_top_json(output_json)
                if data:
                    self._intel_cache = data
                    self._intel_cache_time = time.time()
                    return data
        except Exception:
            pass
        
        return None

    def _get_intel_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get Intel GPU process information using intel_gpu_top.
        
        Uses intel_gpu_top JSON output to get per-process GPU information.
        DRM file descriptor scanning has been removed for performance.
        """
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            data = self._get_intel_gpu_data_cached()
            
            if data and isinstance(data, dict) and 'clients' in data:
                clients = data['clients']
                if isinstance(clients, dict):
                    for client_id, client_info in clients.items():
                        if not isinstance(client_info, dict):
                            continue
                        
                        # PID is nested inside client_info as a string
                        pid_str = client_info.get('pid', '')
                        if not pid_str:
                            continue
                        
                        try:
                            pid = int(pid_str)
                        except (ValueError, TypeError):
                            continue
                        
                        gpu_usage = 0.0
                        video_usage = 0.0
                        
                        # Parse engine-classes (note: hyphen not underscore)
                        engine_classes = client_info.get('engine-classes', {})
                        if isinstance(engine_classes, dict):
                            # Get Render/3D usage for GPU
                            for engine_name in ['Render/3D', 'Render', 'RCS', 'render']:
                                if engine_name in engine_classes:
                                    engine_data = engine_classes[engine_name]
                                    if isinstance(engine_data, dict):
                                        busy = engine_data.get('busy', '0')
                                        try:
                                            gpu_usage = float(busy)
                                        except (ValueError, TypeError):
                                            pass
                                    break
                            
                            # Get Video usage for encoding/decoding
                            for engine_name in ['Video', 'VCS', 'video']:
                                if engine_name in engine_classes:
                                    engine_data = engine_classes[engine_name]
                                    if isinstance(engine_data, dict):
                                        busy = engine_data.get('busy', '0')
                                        try:
                                            video_usage = float(busy)
                                        except (ValueError, TypeError):
                                            pass
                                    break
                        
                        # Include all processes (even 0% usage) to show them in GPU tab
                        processes[pid] = {
                            'gpu_usage': max(0.0, gpu_usage),
                            'gpu_memory': 0,
                            'encoding': max(0.0, video_usage),
                            'decoding': max(0.0, video_usage)
                        }
        except Exception:
            pass
        
        # Note: DRM file descriptor scanning removed for performance
        # intel_gpu_top provides sufficient process detection
        
        return processes
    
    def _get_amd_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get AMD GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Try rocm-smi or radeontop for AMD GPU stats
            # rocm-smi provides better per-process info if available
            try:
                cmd = ['rocm-smi', '--showpid', '--showuse', '--csv']
                output = run_host_command(cmd)
                # Parse rocm-smi output
                for line in output.strip().split('\n'):
                    if not line.strip() or 'GPU' in line or 'PID' in line:
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0])
                            gpu_usage = float(parts[1].rstrip('%')) if '%' in parts[1] else 0.0
                            if pid > 0 and gpu_usage > 0:
                                processes[pid] = {
                                    'gpu_usage': gpu_usage,
                                    'gpu_memory': 0,
                                    'encoding': 0.0,
                                    'decoding': 0.0
                                }
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
            
            # Fallback: radeontop doesn't provide per-process stats easily
            # We'll rely on system-level stats for AMD
            pass
        except Exception:
            pass
        
        return processes
    
    def _get_nvidia_total_stats(self) -> Dict[str, float]:
        """Get total NVIDIA GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            cmd = [
                'nvidia-smi',
                '--query-gpu=utilization.gpu,utilization.enc,utilization.dec',
                '--format=csv,noheader,nounits'
            ]
            output = run_host_command(cmd)
            
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    try:
                        gpu_usage = float(parts[0]) if parts[0] else 0.0
                        enc_usage = float(parts[1]) if parts[1] else 0.0
                        dec_usage = float(parts[2]) if parts[2] else 0.0
                        stats['gpu_usage'] = max(stats['gpu_usage'], gpu_usage)
                        stats['encoding'] = max(stats['encoding'], enc_usage)
                        stats['decoding'] = max(stats['decoding'], dec_usage)
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
        
        return stats
    
    def _get_intel_total_stats(self) -> Dict[str, float]:
        """Get total Intel GPU statistics.
        
        Uses cached intel_gpu_top JSON output to get overall GPU engine usage.
        """
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            # Use cached data to avoid slow intel_gpu_top calls
            data = self._get_intel_gpu_data_cached()
            
            if data and isinstance(data, dict) and 'engines' in data:
                engines = data['engines']
                if isinstance(engines, dict):
                    # Get Render/3D for GPU usage
                    for engine_name in ['Render/3D', 'Render', 'RCS']:
                        if engine_name in engines:
                            engine_data = engines[engine_name]
                            if isinstance(engine_data, dict):
                                busy = engine_data.get('busy', 0)
                                try:
                                    stats['gpu_usage'] = float(busy)
                                except (ValueError, TypeError):
                                    pass
                            break
                    
                    # Get Video for encoding/decoding
                    for engine_name in ['Video', 'VCS']:
                        if engine_name in engines:
                            engine_data = engines[engine_name]
                            if isinstance(engine_data, dict):
                                busy = engine_data.get('busy', 0)
                                try:
                                    video_usage = float(busy)
                                    stats['encoding'] = video_usage
                                    stats['decoding'] = video_usage
                                except (ValueError, TypeError):
                                    pass
                            break
        except Exception:
            pass
        
        return stats
    
    def _get_amd_total_stats(self) -> Dict[str, float]:
        """Get total AMD GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            # Try rocm-smi first (better for newer AMD GPUs)
            try:
                cmd = ['rocm-smi', '--showuse', '--csv']
                output = run_host_command(cmd)
                for line in output.strip().split('\n'):
                    if not line.strip() or 'GPU' in line:
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        try:
                            gpu_usage = float(parts[1].rstrip('%')) if '%' in parts[1] else 0.0
                            stats['gpu_usage'] = max(stats['gpu_usage'], gpu_usage)
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
            
            # Fallback: Try radeontop
            try:
                cmd = ['timeout', '2', 'radeontop', '-l', '1', '-d', '-']
                output = run_host_command(cmd)
                
                # Parse radeontop output
                for line in output.split('\n'):
                    line_lower = line.lower()
                    if ('gpu' in line_lower or 'vram' in line_lower) and '%' in line:
                        try:
                            parts = line.split()
                            for part in parts:
                                if '%' in part:
                                    usage = float(part.rstrip('%'))
                                    stats['gpu_usage'] = max(stats['gpu_usage'], usage)
                                    break
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
        except Exception:
            pass
        
        return stats
