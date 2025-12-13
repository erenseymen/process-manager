# SPDX-License-Identifier: GPL-3.0-or-later
# Intel GPU statistics

"""Intel GPU statistics provider using intel_gpu_top."""

from __future__ import annotations

import json
import time
from typing import Dict, Any, Optional

from .base import GPUProvider
from ...ps_commands import run_host_command


class IntelProvider(GPUProvider):
    """Intel GPU statistics using intel_gpu_top."""
    
    def __init__(self) -> None:
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 1.8
    
    @property
    def vendor_name(self) -> str:
        return 'intel'
    
    def get_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get Intel GPU process information using intel_gpu_top."""
        processes: Dict[int, Dict[str, Any]] = {}
        
        try:
            data = self._get_cached_data()
            
            if data and isinstance(data, dict) and 'clients' in data:
                clients = data['clients']
                if isinstance(clients, dict):
                    for client_id, client_info in clients.items():
                        if not isinstance(client_info, dict):
                            continue
                        
                        pid_str = client_info.get('pid', '')
                        if not pid_str:
                            continue
                        
                        try:
                            pid = int(pid_str)
                        except (ValueError, TypeError):
                            continue
                        
                        gpu_usage = 0.0
                        video_usage = 0.0
                        
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
                        
                        processes[pid] = {
                            'gpu_usage': max(0.0, gpu_usage),
                            'gpu_memory': 0,
                            'encoding': max(0.0, video_usage),
                            'decoding': max(0.0, video_usage)
                        }
        except Exception:
            pass
        
        return processes
    
    def get_total_stats(self) -> Dict[str, float]:
        """Get total Intel GPU statistics."""
        stats = {'gpu_usage': 0.0, 'encoding': 0.0, 'decoding': 0.0}
        
        try:
            data = self._get_cached_data()
            
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
    
    def _get_cached_data(self) -> Optional[Dict[str, Any]]:
        """Get Intel GPU data with caching."""
        now = time.time()
        
        if self._cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._cache
        
        cmd = ['sudo', '-n', 'timeout', '1', 'intel_gpu_top', '-J', '-o', '-']
        try:
            output = run_host_command(cmd, timeout=3)
            
            if output and output.strip():
                data = self._parse_json_output(output)
                if data:
                    self._cache = data
                    self._cache_time = time.time()
                    return data
        except Exception:
            pass
        
        return None
    
    def _parse_json_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse intel_gpu_top JSON output, handling incomplete arrays."""
        if not output or not output.strip():
            return None
        
        output = output.strip()
        
        # Try to parse as complete JSON
        try:
            data = json.loads(output)
            if isinstance(data, list) and len(data) > 0:
                return data[-1]
            elif isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        
        # Try to extract the last complete object
        try:
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
