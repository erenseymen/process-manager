# SPDX-License-Identifier: GPL-3.0-or-later
# AMD GPU statistics

"""AMD GPU statistics provider using rocm-smi and radeontop."""

from __future__ import annotations

from typing import Dict, Any

from .base import GPUProvider
from ...ps_commands import run_host_command


class AMDProvider(GPUProvider):
    """AMD GPU statistics using rocm-smi and radeontop."""
    
    @property
    def vendor_name(self) -> str:
        return 'amd'
    
    def get_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get AMD GPU process information."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Try rocm-smi first (better for per-process info)
            cmd = ['rocm-smi', '--showpid', '--showuse', '--csv']
            output = run_host_command(cmd)
            
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
        
        return processes
    
    def get_total_stats(self) -> Dict[str, float]:
        """Get total AMD GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        # Try rocm-smi first
        if self._try_rocm_smi(stats):
            return stats
        
        # Fallback to radeontop
        self._try_radeontop(stats)
        
        return stats
    
    def _try_rocm_smi(self, stats: Dict[str, float]) -> bool:
        """Try to get stats from rocm-smi."""
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
                        return True
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
        
        return False
    
    def _try_radeontop(self, stats: Dict[str, float]) -> None:
        """Try to get stats from radeontop."""
        try:
            cmd = ['timeout', '2', 'radeontop', '-l', '1', '-d', '-']
            output = run_host_command(cmd)
            
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
