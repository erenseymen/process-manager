# SPDX-License-Identifier: GPL-3.0-or-later
# Port statistics

"""Utilities for retrieving open ports and network connections."""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from .ps_commands import run_host_command

if TYPE_CHECKING:
    pass


class PortStats:
    """Port statistics and monitoring for open ports and network connections."""
    
    def __init__(self) -> None:
        """Initialize PortStats."""
        pass
    
    def get_open_ports(self) -> List[Dict[str, Any]]:
        """Get all open ports with process information.
        
        Uses 'ss' command to get listening ports and established connections.
        
        Returns:
            List of dictionaries with keys:
            - pid: Process ID (int or None)
            - name: Process name (str)
            - protocol: Protocol (tcp, udp, tcp6, udp6)
            - state: Connection state (LISTEN, ESTAB, etc.)
            - local_address: Local IP address (str)
            - local_port: Local port number (int)
            - remote_address: Remote IP address (str, optional)
            - remote_port: Remote port number (int, optional)
        """
        ports: List[Dict[str, Any]] = []
        
        try:
            # Use ss command to get all listening and established connections
            # -t: TCP
            # -u: UDP
            # -n: Numeric addresses/ports
            # -p: Show process information
            # -l: Listening sockets
            # -a: All sockets (listening and established)
            cmd = ['ss', '-tunap']
            output = run_host_command(cmd, timeout=5)
            
            for line in output.strip().split('\n'):
                if not line.strip() or line.startswith('State'):
                    continue
                
                try:
                    # Parse ss output
                    # Format: State   Recv-Q   Send-Q   Local Address:Port   Peer Address:Port   Process
                    # Example: LISTEN 0      128           0.0.0.0:22         0.0.0.0:*      users:(("sshd",pid=1234,fd=3))
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    
                    state = parts[0]
                    local_addr_port = parts[4]
                    remote_addr_port = parts[5] if len(parts) > 5 else None
                    
                    # Extract process info from the end of the line
                    process_info = None
                    pid = None
                    name = None
                    
                    # Look for process info in format: users:(("name",pid=1234,fd=3))
                    process_match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                    if process_match:
                        name = process_match.group(1)
                        pid = int(process_match.group(2))
                    else:
                        # Try alternative format: users:(("name",pid=1234))
                        process_match = re.search(r'\(\("([^"]+)",pid=(\d+)\)', line)
                        if process_match:
                            name = process_match.group(1)
                            pid = int(process_match.group(2))
                    
                    # Parse local address and port
                    if ':' in local_addr_port:
                        local_addr, local_port_str = local_addr_port.rsplit(':', 1)
                        try:
                            local_port = int(local_port_str)
                        except ValueError:
                            continue
                    else:
                        continue
                    
                    # Parse remote address and port (if present)
                    remote_addr = None
                    remote_port = None
                    if remote_addr_port and remote_addr_port != '*':
                        if ':' in remote_addr_port:
                            remote_addr, remote_port_str = remote_addr_port.rsplit(':', 1)
                            try:
                                remote_port = int(remote_port_str) if remote_port_str != '*' else None
                            except ValueError:
                                remote_port = None
                        else:
                            remote_addr = remote_addr_port
                    
                    # Determine protocol
                    protocol = 'tcp'
                    if line.startswith('udp'):
                        protocol = 'udp'
                    elif 'tcp' in line.lower():
                        protocol = 'tcp'
                    
                    # Check for IPv6
                    if '::' in local_addr or (remote_addr and '::' in remote_addr):
                        protocol = protocol + '6'
                    
                    ports.append({
                        'pid': pid,
                        'name': name or 'N/A',
                        'protocol': protocol,
                        'state': state,
                        'local_address': local_addr,
                        'local_port': local_port,
                        'remote_address': remote_addr,
                        'remote_port': remote_port
                    })
                    
                except (ValueError, IndexError, AttributeError) as e:
                    # Skip lines that can't be parsed
                    continue
                    
        except (OSError, subprocess.SubprocessError):
            pass
        
        return ports
    
    def get_ports_by_pid(self, pid: int) -> List[Dict[str, Any]]:
        """Get open ports for a specific process.
        
        Args:
            pid: Process ID to get ports for.
            
        Returns:
            List of port dictionaries (same format as get_open_ports).
        """
        all_ports = self.get_open_ports()
        return [p for p in all_ports if p.get('pid') == pid]

