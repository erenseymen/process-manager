# SPDX-License-Identifier: GPL-3.0-or-later
# NVIDIA GPU statistics

"""NVIDIA GPU statistics provider using nvidia-smi."""

from __future__ import annotations

from typing import Dict, Any

from .base import GPUProvider
from ...ps_commands import run_host_command


class NvidiaProvider(GPUProvider):
    """NVIDIA GPU statistics using nvidia-smi."""
    
    @property
    def vendor_name(self) -> str:
        return 'nvidia'
    
    def get_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get NVIDIA GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Get processes with memory usage
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
            
            # Get per-process GPU utilization
            self._update_gpu_utilization(processes)
            
            # Get encoding/decoding info
            self._update_encoder_stats(processes)
                
        except Exception:
            pass
        
        return processes
    
    def _update_gpu_utilization(self, processes: Dict[int, Dict[str, Any]]) -> None:
        """Update GPU utilization for processes."""
        try:
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
                            processes[pid]['gpu_usage'] = sm_usage
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
    
    def _update_encoder_stats(self, processes: Dict[int, Dict[str, Any]]) -> None:
        """Update encoding/decoding stats for processes."""
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
                                processes[pid]['encoding'] = 30.0
                            elif 'decode' in codec_type:
                                processes[pid]['decoding'] = 30.0
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
    
    def get_total_stats(self) -> Dict[str, float]:
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
