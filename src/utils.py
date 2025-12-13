# SPDX-License-Identifier: GPL-3.0-or-later
# Utility functions

from typing import Union


def parse_size_str(s: str) -> float:
    """
    Parse a human-readable size string (e.g. '1.5 MiB', '256 KiB') to bytes.
    Handles /s suffix by stripping it (for rates).
    Returns 0 on failure or empty input.
    """
    if not s or s == '-':
        return 0.0
    
    s = s.strip()
    if s.endswith('/s'):
        s = s[:-2].strip()
        
    try:
        if s.endswith('TiB'):
            return float(s[:-3]) * 1024**4
        elif s.endswith('GiB'):
            return float(s[:-3]) * 1024**3
        elif s.endswith('MiB'):
            return float(s[:-3]) * 1024**2
        elif s.endswith('KiB'):
            return float(s[:-3]) * 1024
        elif s.endswith('B'):
            return float(s[:-1])
        else:
            return float(s)
    except (ValueError, AttributeError):
        return 0.0


def format_bytes(bytes_val: Union[int, float]) -> str:
    """
    Format bytes to human-readable string (e.g., '1.5 GiB', '256 MiB').
    
    Args:
        bytes_val: Number of bytes to format.
        
    Returns:
        Formatted string with appropriate unit.
    """
    if bytes_val >= 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f} GiB"
    elif bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MiB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KiB"
    return f"{int(bytes_val)} B"


def format_rate(bytes_per_sec: Union[int, float]) -> str:
    """
    Format I/O rate to human-readable string.
    
    Same as format_bytes but intended for rate values.
    
    Args:
        bytes_per_sec: Bytes per second to format.
        
    Returns:
        Formatted string with appropriate unit.
    """
    return format_bytes(bytes_per_sec)

