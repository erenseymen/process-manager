# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple

from .ps_commands import run_host_command, is_flatpak

if TYPE_CHECKING:
    pass


class GPUStats:
    """GPU statistics and monitoring for Intel, NVIDIA, and AMD GPUs."""
    
    def __init__(self) -> None:
        self.gpu_types: List[str] = []
        self._detect_gpus()
    
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
        """Get Intel GPU process information using intel_gpu_top.
        
        Uses intel_gpu_top as the only method for detecting Intel GPU processes.
        """
        processes: Dict[int, Dict[str, Any]] = {}
        
        # Use intel_gpu_top (user-requested dependency)
        try:
            # Check if intel_gpu_top is available
            cmd_check = ['intel_gpu_top', '-h']
            result = subprocess.run(
                cmd_check,
                capture_output=True,
                text=True,
                timeout=2
            )
            # If help works, the command is available
            if result.returncode not in [0, 1]:  # Not available if help doesn't work
                return processes
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return processes
        
        # Try intel_gpu_top JSON output
        try:
            # Try JSON output format
            cmd_json = ['intel_gpu_top', '-J', '-l', '1', '-s', '500']
            result = subprocess.run(
                cmd_json,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    # Parse JSON structure (format may vary)
                    if isinstance(data, dict):
                        # Look for processes in various possible JSON structures
                        proc_data = {}
                        if 'processes' in data:
                            proc_data = data['processes']
                        elif 'engines' in data and isinstance(data['engines'], dict):
                            # Sometimes processes are nested under engines
                            for key, value in data['engines'].items():
                                if isinstance(value, dict) and 'processes' in value:
                                    proc_data.update(value['processes'])
                        
                        for pid_str, proc_info in proc_data.items():
                            try:
                                pid = int(pid_str)
                                if isinstance(proc_info, dict):
                                    gpu_usage = float(proc_info.get('gpu', proc_info.get('GPU', proc_info.get('render', 0))))
                                    video_usage = float(proc_info.get('video', proc_info.get('Video', proc_info.get('vcs', 0))))
                                    # Include processes even with 0% usage to make them visible
                                    processes[pid] = {
                                        'gpu_usage': max(0.0, gpu_usage),
                                        'gpu_memory': 0,
                                        'encoding': max(0.0, video_usage),
                                        'decoding': max(0.0, video_usage)
                                    }
                            except (ValueError, KeyError, TypeError):
                                continue
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
            pass
        
        # If JSON format didn't work, try CSV format as fallback
        if not processes:
            try:
                cmd_csv = ['intel_gpu_top', '-c', '-l', '1', '-s', '500']
                result = subprocess.run(
                    cmd_csv,
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0 and result.stdout and result.stdout.strip():
                    # Parse CSV format - typically has headers and process rows
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        # Skip header line, parse process rows
                        for line in lines[1:]:
                            parts = [p.strip() for p in line.split(',')]
                            # CSV format may vary, try to extract PID and usage info
                            # This is a basic parser - may need adjustment based on actual format
                            if len(parts) >= 3:
                                try:
                                    # Look for PID in the line
                                    for part in parts:
                                        if part.isdigit() and int(part) > 0:
                                            pid = int(part)
                                            # Try to find usage percentages
                                            gpu_usage = 0.0
                                            video_usage = 0.0
                                            for p in parts:
                                                if '%' in p:
                                                    try:
                                                        val = float(p.rstrip('%'))
                                                        if 'video' in line.lower() or 'vcs' in line.lower():
                                                            video_usage = max(video_usage, val)
                                                        else:
                                                            gpu_usage = max(gpu_usage, val)
                                                    except ValueError:
                                                        pass
                                            
                                            if pid not in processes:
                                                processes[pid] = {
                                                    'gpu_usage': max(0.0, gpu_usage),
                                                    'gpu_memory': 0,
                                                    'encoding': max(0.0, video_usage),
                                                    'decoding': max(0.0, video_usage)
                                                }
                                            break
                                except (ValueError, IndexError):
                                    continue
            except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
                pass
        
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

