# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics

from __future__ import annotations

import subprocess
import json
from typing import TYPE_CHECKING, Dict, List, Optional, Any

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
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                self.gpu_types.append('nvidia')
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        
        # Check for Intel GPU
        try:
            result = subprocess.run(
                ['intel_gpu_top', '-l'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self.gpu_types.append('intel')
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # Also check /sys/class/drm for Intel GPU
            try:
                import os
                if any(os.path.exists(f'/sys/class/drm/card{i}/device/vendor') 
                       for i in range(10)):
                    # Check if it's Intel (vendor ID 0x8086)
                    for i in range(10):
                        vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                        if os.path.exists(vendor_path):
                            with open(vendor_path, 'r') as f:
                                vendor_id = f.read().strip()
                                if vendor_id == '0x8086':
                                    self.gpu_types.append('intel')
                                    break
            except (OSError, IOError):
                pass
        
        # Check for AMD GPU
        try:
            result = subprocess.run(
                ['radeontop', '-l', '1', '-d', '-'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self.gpu_types.append('amd')
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # Also check /sys/class/drm for AMD GPU
            try:
                import os
                for i in range(10):
                    vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                    if os.path.exists(vendor_path):
                        with open(vendor_path, 'r') as f:
                            vendor_id = f.read().strip()
                            # AMD vendor IDs: 0x1002 (AMD), 0x1022 (AMD/ATI)
                            if vendor_id in ['0x1002', '0x1022']:
                                self.gpu_types.append('amd')
                                break
            except (OSError, IOError):
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
            # Use nvidia-smi to get process info
            cmd = [
                'nvidia-smi',
                '--query-compute-apps=pid,used_memory,process_name',
                '--format=csv,noheader,nounits'
            ]
            output = run_host_command(cmd)
            
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split(', ')
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        memory_mb = int(parts[1])
                        processes[pid] = {
                            'gpu_usage': 0.0,  # nvidia-smi doesn't provide per-process GPU usage easily
                            'gpu_memory': memory_mb * 1024 * 1024,
                            'encoding': 0.0,
                            'decoding': 0.0
                        }
                    except (ValueError, IndexError):
                        continue
            
            # Try to get encoding/decoding info
            try:
                cmd = [
                    'nvidia-smi',
                    '--query-encoder-sessions=pid,codec_type,codec_name',
                    '--format=csv,noheader'
                ]
                output = run_host_command(cmd)
                for line in output.strip().split('\n'):
                    if not line.strip():
                        continue
                    parts = line.split(', ')
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0])
                            codec_type = parts[1].lower()
                            if pid in processes:
                                if 'encode' in codec_type:
                                    processes[pid]['encoding'] = 50.0  # Estimate
                                elif 'decode' in codec_type:
                                    processes[pid]['decoding'] = 50.0  # Estimate
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass
                
        except Exception:
            pass
        
        return processes
    
    def _get_intel_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get Intel GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Use intel_gpu_top or /sys/class/drm
            # For now, try to read from /sys/class/drm
            import os
            import glob
            
            # Try intel_gpu_top first (if available)
            try:
                cmd = ['timeout', '1', 'intel_gpu_top', '-l', '1', '-s', '100']
                output = run_host_command(cmd)
                # Parse intel_gpu_top output (complex, simplified here)
                # This is a simplified parser - real implementation would need more work
            except Exception:
                pass
            
            # Fallback: try to get info from /sys/class/drm
            # Intel GPU doesn't provide easy per-process stats, so we'll estimate
            # based on video codec usage
            try:
                # Check for video codec usage in /sys/class/drm
                for card_path in glob.glob('/sys/class/drm/card*/device'):
                    if os.path.exists(card_path):
                        # Check if Intel GPU
                        vendor_path = os.path.join(card_path, 'vendor')
                        if os.path.exists(vendor_path):
                            with open(vendor_path, 'r') as f:
                                if f.read().strip() == '0x8086':
                                    # Intel GPU found, but per-process stats are limited
                                    # We'll return empty for now and rely on system-level stats
                                    pass
            except Exception:
                pass
                
        except Exception:
            pass
        
        return processes
    
    def _get_amd_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get AMD GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # AMD doesn't provide easy per-process stats
            # radeontop shows overall GPU usage but not per-process
            # We'll return empty for now
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
                parts = line.split(', ')
                if len(parts) >= 3:
                    try:
                        gpu_usage = float(parts[0])
                        enc_usage = float(parts[1])
                        dec_usage = float(parts[2])
                        stats['gpu_usage'] = max(stats['gpu_usage'], gpu_usage)
                        stats['encoding'] = max(stats['encoding'], enc_usage)
                        stats['decoding'] = max(stats['decoding'], dec_usage)
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
        
        return stats
    
    def _get_intel_total_stats(self) -> Dict[str, float]:
        """Get total Intel GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            # Try intel_gpu_top
            cmd = ['timeout', '1', 'intel_gpu_top', '-l', '1', '-s', '100', '-o', '-']
            output = run_host_command(cmd)
            
            # Parse intel_gpu_top output (simplified)
            # Real implementation would need proper parsing
            for line in output.split('\n'):
                if 'GPU' in line and '%' in line:
                    try:
                        # Extract GPU usage percentage
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if '%' in part:
                                usage = float(part.rstrip('%'))
                                stats['gpu_usage'] = max(stats['gpu_usage'], usage)
                                break
                    except (ValueError, IndexError):
                        continue
        except Exception:
            # Fallback: try /sys/class/drm
            try:
                import os
                import glob
                for card_path in glob.glob('/sys/class/drm/card*/device'):
                    if os.path.exists(os.path.join(card_path, 'vendor')):
                        # Intel GPU stats from sysfs are limited
                        pass
            except Exception:
                pass
        
        return stats
    
    def _get_amd_total_stats(self) -> Dict[str, float]:
        """Get total AMD GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            # Try radeontop
            cmd = ['timeout', '1', 'radeontop', '-l', '1', '-d', '-']
            output = run_host_command(cmd)
            
            # Parse radeontop output (simplified)
            for line in output.split('\n'):
                if 'gpu' in line.lower() and '%' in line:
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
        
        return stats

