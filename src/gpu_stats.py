# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics

from __future__ import annotations

import glob
import json
import os
import subprocess
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple

from .ps_commands import run_host_command, is_flatpak

if TYPE_CHECKING:
    pass


class GPUStats:
    """GPU statistics and monitoring for Intel, NVIDIA, and AMD GPUs."""
    
    def __init__(self) -> None:
        self.gpu_types: List[str] = []
        self._detect_gpus()
        # Cache for Intel fdinfo readings (for calculating usage percentages)
        self._intel_fdinfo_cache: Dict[int, Dict[str, Any]] = {}
        self._intel_fdinfo_timestamp: float = 0.0
    
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
    
    def get_gpu_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get GPU usage per process.
        
        Returns:
            Dictionary mapping PID to GPU usage info:
            {
                pid: {
                    'gpu_usage': float,  # Percentage
                    'gpu_memory': int,   # Bytes
                    'encoding': float,   # Percentage (if available)
                    'decoding': float,   # Percentage (if available)
                    'gpu_type': str      # 'nvidia', 'intel', or 'amd'
                }
            }
        """
        processes: Dict[int, Dict[str, Any]] = {}
        
        if 'nvidia' in self.gpu_types:
            nvidia_procs = self._get_nvidia_processes()
            for pid, info in nvidia_procs.items():
                if pid not in processes:
                    processes[pid] = {}
                processes[pid].update(info)
                processes[pid]['gpu_type'] = 'nvidia'
        
        if 'intel' in self.gpu_types:
            intel_procs = self._get_intel_processes()
            for pid, info in intel_procs.items():
                if pid not in processes:
                    processes[pid] = {}
                # Merge with existing or create new
                if 'gpu_usage' in processes[pid]:
                    # If multiple GPUs, sum the usage
                    processes[pid]['gpu_usage'] = processes[pid].get('gpu_usage', 0) + info.get('gpu_usage', 0)
                else:
                    processes[pid]['gpu_usage'] = info.get('gpu_usage', 0)
                processes[pid]['encoding'] = processes[pid].get('encoding', 0) + info.get('encoding', 0)
                processes[pid]['decoding'] = processes[pid].get('decoding', 0) + info.get('decoding', 0)
                processes[pid]['gpu_type'] = 'intel'
        
        if 'amd' in self.gpu_types:
            amd_procs = self._get_amd_processes()
            for pid, info in amd_procs.items():
                if pid not in processes:
                    processes[pid] = {}
                if 'gpu_usage' in processes[pid]:
                    processes[pid]['gpu_usage'] = processes[pid].get('gpu_usage', 0) + info.get('gpu_usage', 0)
                else:
                    processes[pid]['gpu_usage'] = info.get('gpu_usage', 0)
                processes[pid]['gpu_type'] = 'amd'
        
        return processes
    
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
                
        except Exception as e:
            # Debug: print error if needed
            pass
        
        return processes
    
    def _get_intel_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get Intel GPU process information.
        
        Uses /proc/[pid]/fdinfo to read DRM engine usage statistics.
        This works on modern Linux kernels (5.19+) without requiring intel_gpu_top.
        """
        processes: Dict[int, Dict[str, Any]] = {}
        
        # First try the fdinfo method (works without intel_gpu_top)
        fdinfo_processes = self._get_intel_fdinfo_processes()
        if fdinfo_processes:
            processes.update(fdinfo_processes)
            return processes
        
        # Fallback: Try intel_gpu_top if fdinfo method didn't work
        try:
            # intel_gpu_top format: PID Name GPU% Render% Blitter% Video% VideoEU%
            # Use -J for JSON output if available, otherwise parse text
            cmd_json = ['timeout', '2', 'intel_gpu_top', '-J', '-l', '1', '-s', '500']
            try:
                output_json = run_host_command(cmd_json)
                if output_json and output_json.strip():
                    # Try to parse JSON output
                    data = json.loads(output_json)
                    # Parse JSON structure (format may vary)
                    if 'engines' in data or 'processes' in data:
                        # Extract process data from JSON
                        proc_data = data.get('processes', data.get('engines', {}))
                        for pid_str, proc_info in proc_data.items():
                            try:
                                pid = int(pid_str)
                                gpu_usage = float(proc_info.get('gpu', proc_info.get('GPU', 0)))
                                video_usage = float(proc_info.get('video', proc_info.get('Video', 0)))
                                if gpu_usage > 0 or video_usage > 0:
                                    processes[pid] = {
                                        'gpu_usage': gpu_usage,
                                        'gpu_memory': 0,
                                        'encoding': video_usage if video_usage > 0 else 0.0,
                                        'decoding': 0.0
                                    }
                            except (ValueError, KeyError):
                                continue
            except Exception:
                pass
        except Exception:
            pass
        
        return processes
    
    def _get_intel_fdinfo_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get Intel GPU process info from /proc/[pid]/fdinfo.
        
        Modern Linux kernels expose DRM engine usage in fdinfo files.
        Format: drm-engine-<name>: <ns> ns
        """
        processes: Dict[int, Dict[str, Any]] = {}
        current_time = time.time()
        
        # Collect current fdinfo readings
        current_readings: Dict[int, Dict[str, int]] = {}
        
        try:
            # Iterate through all processes
            for proc_dir in glob.glob('/proc/[0-9]*'):
                try:
                    pid = int(os.path.basename(proc_dir))
                    fdinfo_dir = os.path.join(proc_dir, 'fdinfo')
                    
                    if not os.path.isdir(fdinfo_dir):
                        continue
                    
                    # Check each fd for DRM engine info
                    render_ns = 0
                    video_ns = 0
                    found_drm = False
                    
                    for fd_file in os.listdir(fdinfo_dir):
                        fd_path = os.path.join(fdinfo_dir, fd_file)
                        try:
                            with open(fd_path, 'r') as f:
                                content = f.read()
                                
                            # Look for Intel GPU specific drm-engine entries
                            if 'drm-engine-render:' in content or 'drm-engine-video:' in content:
                                found_drm = True
                                for line in content.split('\n'):
                                    line = line.strip()
                                    if line.startswith('drm-engine-render:'):
                                        try:
                                            # Format: "drm-engine-render: 1234567890 ns"
                                            val = line.split(':')[1].strip().split()[0]
                                            render_ns = max(render_ns, int(val))
                                        except (ValueError, IndexError):
                                            pass
                                    elif line.startswith('drm-engine-video:'):
                                        try:
                                            val = line.split(':')[1].strip().split()[0]
                                            video_ns = max(video_ns, int(val))
                                        except (ValueError, IndexError):
                                            pass
                        except (OSError, IOError, PermissionError):
                            continue
                    
                    if found_drm:
                        current_readings[pid] = {
                            'render_ns': render_ns,
                            'video_ns': video_ns
                        }
                        
                except (ValueError, OSError, PermissionError):
                    continue
                    
        except Exception:
            pass
        
        # Calculate usage percentages from delta between readings
        time_delta = current_time - self._intel_fdinfo_timestamp
        
        # If we have cached data and enough time has passed, calculate usage
        if time_delta > 0.1 and self._intel_fdinfo_cache:  # Need at least 100ms between readings
            for pid, current in current_readings.items():
                if pid in self._intel_fdinfo_cache:
                    prev = self._intel_fdinfo_cache[pid]
                    
                    # Calculate delta in nanoseconds
                    render_delta = current['render_ns'] - prev['render_ns']
                    video_delta = current['video_ns'] - prev['video_ns']
                    
                    # Convert to percentage (time_delta is in seconds, deltas are in ns)
                    # time_delta * 1e9 = time delta in nanoseconds
                    time_delta_ns = time_delta * 1e9
                    
                    if time_delta_ns > 0:
                        render_pct = min(100.0, (render_delta / time_delta_ns) * 100.0)
                        video_pct = min(100.0, (video_delta / time_delta_ns) * 100.0)
                        
                        # Include process if there's actual usage or if it has DRM file descriptors
                        # (show processes even with 0% usage so they're visible in the list)
                        processes[pid] = {
                            'gpu_usage': max(0.0, render_pct),
                            'gpu_memory': 0,
                            'encoding': max(0.0, video_pct),  # Video engine handles both enc/dec
                            'decoding': max(0.0, video_pct)
                        }
        else:
            # First call or not enough time passed: return processes with DRM file descriptors
            # but with 0% usage (they'll show up in the list and usage will be calculated next time)
            for pid in current_readings.keys():
                processes[pid] = {
                    'gpu_usage': 0.0,
                    'gpu_memory': 0,
                    'encoding': 0.0,
                    'decoding': 0.0
                }
        
        # Update cache
        self._intel_fdinfo_cache = current_readings
        self._intel_fdinfo_timestamp = current_time
        
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
    
    def get_total_gpu_stats(self) -> Dict[str, Any]:
        """Get total GPU usage statistics.
        
        Returns:
            Dictionary with total GPU stats:
            {
                'total_gpu_usage': float,      # Percentage
                'total_encoding': float,       # Percentage
                'total_decoding': float,       # Percentage
                'gpu_types': List[str]         # Available GPU types
            }
        """
        stats = {
            'total_gpu_usage': 0.0,
            'total_encoding': 0.0,
            'total_decoding': 0.0,
            'gpu_types': self.gpu_types.copy()
        }
        
        if 'nvidia' in self.gpu_types:
            nvidia_stats = self._get_nvidia_total_stats()
            stats['total_gpu_usage'] = max(stats['total_gpu_usage'], nvidia_stats.get('gpu_usage', 0))
            stats['total_encoding'] = max(stats['total_encoding'], nvidia_stats.get('encoding', 0))
            stats['total_decoding'] = max(stats['total_decoding'], nvidia_stats.get('decoding', 0))
        
        if 'intel' in self.gpu_types:
            intel_stats = self._get_intel_total_stats()
            stats['total_gpu_usage'] = max(stats['total_gpu_usage'], intel_stats.get('gpu_usage', 0))
            stats['total_encoding'] = max(stats['total_encoding'], intel_stats.get('encoding', 0))
            stats['total_decoding'] = max(stats['total_decoding'], intel_stats.get('decoding', 0))
        
        if 'amd' in self.gpu_types:
            amd_stats = self._get_amd_total_stats()
            stats['total_gpu_usage'] = max(stats['total_gpu_usage'], amd_stats.get('gpu_usage', 0))
            stats['total_encoding'] = max(stats['total_encoding'], amd_stats.get('encoding', 0))
            stats['total_decoding'] = max(stats['total_decoding'], amd_stats.get('decoding', 0))
        
        return stats
    
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
        except Exception as e:
            # Debug: could log error here
            pass
        
        return stats
    
    def _get_intel_total_stats(self) -> Dict[str, float]:
        """Get total Intel GPU statistics.
        
        Aggregates per-process stats to get total GPU usage.
        """
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        # Get per-process stats and sum them up
        processes = self._get_intel_processes()
        if processes:
            total_gpu = 0.0
            total_video = 0.0
            for proc_info in processes.values():
                total_gpu += proc_info.get('gpu_usage', 0)
                total_video += proc_info.get('encoding', 0)
            
            # Cap at 100%
            stats['gpu_usage'] = min(100.0, total_gpu)
            stats['encoding'] = min(100.0, total_video)
            stats['decoding'] = min(100.0, total_video)
            return stats
        
        # Fallback: Try intel_gpu_top for overall stats
        try:
            cmd = ['timeout', '2', 'intel_gpu_top', '-l', '1', '-s', '500', '-o', '-']
            output = run_host_command(cmd)
            
            # Parse intel_gpu_top output
            # Look for summary lines with GPU usage
            for line in output.split('\n'):
                line_lower = line.lower()
                if ('gpu' in line_lower or 'render' in line_lower) and '%' in line:
                    try:
                        parts = line.split()
                        for part in parts:
                            if '%' in part:
                                usage = float(part.rstrip('%'))
                                if 'gpu' in line_lower or 'render' in line_lower:
                                    stats['gpu_usage'] = max(stats['gpu_usage'], usage)
                                elif 'video' in line_lower or 'encode' in line_lower:
                                    stats['encoding'] = max(stats['encoding'], usage)
                                elif 'decode' in line_lower:
                                    stats['decoding'] = max(stats['decoding'], usage)
                    except (ValueError, IndexError):
                        continue
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

