# SPDX-License-Identifier: GPL-3.0-or-later
# GPU detection utilities

"""GPU detection and vendor identification."""

from __future__ import annotations

import os
import subprocess
from typing import List

from ...ps_commands import run_host_command


def detect_gpus() -> List[str]:
    """Detect available GPU types.
    
    Returns:
        List of detected GPU vendor names: 'nvidia', 'intel', 'amd'
    """
    gpu_types: List[str] = []
    
    # Check for NVIDIA GPU
    if _detect_nvidia():
        gpu_types.append('nvidia')
    
    # Check for Intel GPU
    if _detect_intel():
        gpu_types.append('intel')
    
    # Check for AMD GPU
    if _detect_amd():
        gpu_types.append('amd')
    
    return gpu_types


def _detect_nvidia() -> bool:
    """Detect NVIDIA GPU presence."""
    try:
        cmd = ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader']
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
        
        # Try via flatpak-spawn if direct call failed
        result = run_host_command(cmd)
        if result.strip():
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        try:
            result = run_host_command(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])
            if result.strip():
                return True
        except Exception:
            pass
    
    return False


def _detect_intel() -> bool:
    """Detect Intel GPU presence."""
    # First, check /sys/class/drm for Intel vendor ID (most reliable method)
    for i in range(10):
        vendor_path = f'/sys/class/drm/card{i}/device/vendor'
        if os.path.exists(vendor_path):
            try:
                with open(vendor_path, 'r') as f:
                    vendor_id = f.read().strip()
                    if vendor_id == '0x8086':
                        return True
            except (OSError, IOError):
                pass
    
    # Fallback: try intel_gpu_top command
    try:
        result = subprocess.run(
            ['intel_gpu_top', '-l'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        try:
            result = run_host_command(['intel_gpu_top', '-l'])
            if result is not None:
                # Re-check vendor ID to confirm
                for i in range(10):
                    vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                    if os.path.exists(vendor_path):
                        try:
                            with open(vendor_path, 'r') as f:
                                vendor_id = f.read().strip()
                                if vendor_id == '0x8086':
                                    return True
                        except (OSError, IOError):
                            pass
        except Exception:
            pass
    
    return False


def _detect_amd() -> bool:
    """Detect AMD GPU presence."""
    # Check /sys/class/drm for AMD vendor ID
    for i in range(10):
        vendor_path = f'/sys/class/drm/card{i}/device/vendor'
        if os.path.exists(vendor_path):
            try:
                with open(vendor_path, 'r') as f:
                    vendor_id = f.read().strip()
                    # AMD vendor IDs: 0x1002 (AMD), 0x1022 (AMD/ATI)
                    if vendor_id in ['0x1002', '0x1022']:
                        return True
            except (OSError, IOError):
                pass
    
    # Fallback: try radeontop command
    try:
        result = subprocess.run(
            ['radeontop', '-l', '1', '-d', '-'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    
    return False
