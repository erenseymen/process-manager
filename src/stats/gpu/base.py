# SPDX-License-Identifier: GPL-3.0-or-later
# GPU statistics base classes

"""Base classes and protocols for GPU statistics providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any


class GPUProvider(ABC):
    """Abstract base class for GPU vendor-specific implementations."""
    
    @abstractmethod
    def get_processes(self) -> Dict[int, Dict[str, Any]]:
        """Get GPU usage per process.
        
        Returns:
            Dictionary mapping PID to GPU usage info with keys:
            - gpu_usage: GPU usage percentage (float)
            - gpu_memory: GPU memory usage in bytes (int)
            - encoding: Video encoding usage percentage (float)
            - decoding: Video decoding usage percentage (float)
        """
        pass
    
    @abstractmethod
    def get_total_stats(self) -> Dict[str, float]:
        """Get total GPU statistics.
        
        Returns:
            Dictionary with keys:
            - gpu_usage: Total GPU usage percentage
            - encoding: Video encoding usage percentage
            - decoding: Video decoding usage percentage
        """
        pass
    
    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return the vendor name (e.g., 'nvidia', 'intel', 'amd')."""
        pass
