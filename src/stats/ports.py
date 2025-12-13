# SPDX-License-Identifier: GPL-3.0-or-later
# Port statistics

"""Utilities for retrieving open ports and network connections."""

from __future__ import annotations

import re
import subprocess
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple

from ..ps_commands import run_host_command

if TYPE_CHECKING:
    pass


class PortStats:
    """Port statistics and monitoring for open ports and network connections."""
    
    def __init__(self) -> None:
        """Initialize PortStats."""
        # Cache for traffic statistics: key is (pid, local_addr, local_port, remote_addr, remote_port)
        # Value is (bytes_sent, bytes_recv, timestamp)
        self._traffic_cache: Dict[Tuple[int, str, int, Optional[str], Optional[int]], Tuple[int, int, float]] = {}
    
    def _get_connection_key(self, port: Dict[str, Any]) -> Optional[Tuple[int, str, int, Optional[str], Optional[int]]]:
        """Generate a unique key for a connection for traffic tracking."""
        pid = port.get('pid')
        if pid is None:
            return None
        return (
            pid,
            port.get('local_address', ''),
            port.get('local_port', 0),
            port.get('remote_address'),
            port.get('remote_port')
        )
    
    def get_open_ports(self) -> List[Dict[str, Any]]:
        """Get all open ports with process information and traffic statistics.
        
        Uses 'ss' command to get listening ports and established connections.
        Also collects traffic statistics using 'ss -i' for established connections.
        
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
            - bytes_sent: Total bytes sent (int, 0 if not available)
            - bytes_recv: Total bytes received (int, 0 if not available)
            - bytes_sent_rate: Bytes sent per second (float, 0 if not available)
            - bytes_recv_rate: Bytes received per second (float, 0 if not available)
        """
        ports: List[Dict[str, Any]] = []
        current_time = time.time()
        
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
            
            # Get traffic statistics for established TCP connections
            # Use ss -i to get interface statistics (bytes sent/received)
            traffic_data: Dict[Tuple[int, str, int, Optional[str], Optional[int]], Tuple[int, int]] = {}
            try:
                cmd_traffic = ['ss', '-tunapi']
                output_traffic = run_host_command(cmd_traffic, timeout=5)
                traffic_data = self._parse_traffic_stats(output_traffic)
            except (OSError, subprocess.SubprocessError):
                # Traffic stats not available, continue without them
                pass
            
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
                    # Handle IPv6 addresses with brackets: [::1]:8080
                    local_addr = None
                    local_port = None
                    if local_addr_port.startswith('['):
                        # IPv6 with brackets: [::1]:8080
                        bracket_end = local_addr_port.find(']')
                        if bracket_end > 0 and bracket_end < len(local_addr_port) - 1:
                            local_addr = local_addr_port[1:bracket_end]
                            if local_addr_port[bracket_end + 1] == ':':
                                try:
                                    local_port = int(local_addr_port[bracket_end + 2:])
                                except ValueError:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    elif ':' in local_addr_port:
                        # IPv4 or IPv6 without brackets: 127.0.0.1:8080 or ::1:8080
                        # For IPv6 without brackets, rsplit will work but may be ambiguous
                        # Try to detect if it's IPv6 (contains ::) and handle accordingly
                        if '::' in local_addr_port:
                            # IPv6 without brackets - count colons to find port separator
                            # Format: ::1:8080 - last colon before port
                            parts = local_addr_port.rsplit(':', 1)
                            if len(parts) == 2:
                                local_addr = parts[0]
                                try:
                                    local_port = int(parts[1])
                                except ValueError:
                                    continue
                            else:
                                continue
                        else:
                            # IPv4: 127.0.0.1:8080
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
                        # Handle IPv6 addresses with brackets: [::1]:8080
                        if remote_addr_port.startswith('['):
                            bracket_end = remote_addr_port.find(']')
                            if bracket_end > 0 and bracket_end < len(remote_addr_port) - 1:
                                remote_addr = remote_addr_port[1:bracket_end]
                                if remote_addr_port[bracket_end + 1] == ':':
                                    try:
                                        remote_port = int(remote_addr_port[bracket_end + 2:]) if remote_addr_port[bracket_end + 2:] != '*' else None
                                    except ValueError:
                                        remote_port = None
                        elif ':' in remote_addr_port:
                            # IPv4 or IPv6 without brackets
                            if '::' in remote_addr_port:
                                # IPv6 without brackets
                                parts = remote_addr_port.rsplit(':', 1)
                                if len(parts) == 2:
                                    remote_addr = parts[0]
                                    try:
                                        remote_port = int(parts[1]) if parts[1] != '*' else None
                                    except ValueError:
                                        remote_port = None
                            else:
                                # IPv4
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
                    
                    port_dict = {
                        'pid': pid,
                        'name': name or 'N/A',
                        'protocol': protocol,
                        'state': state,
                        'local_address': local_addr,
                        'local_port': local_port,
                        'remote_address': remote_addr,
                        'remote_port': remote_port,
                        'bytes_sent': 0,
                        'bytes_recv': 0,
                        'bytes_sent_rate': 0.0,
                        'bytes_recv_rate': 0.0
                    }
                    
                    # Add traffic statistics if available
                    conn_key = self._get_connection_key(port_dict)
                    if conn_key and conn_key in traffic_data:
                        bytes_sent, bytes_recv = traffic_data[conn_key]
                        port_dict['bytes_sent'] = bytes_sent
                        port_dict['bytes_recv'] = bytes_recv
                        
                        # Calculate rates using cache
                        if conn_key in self._traffic_cache:
                            old_sent, old_recv, old_time = self._traffic_cache[conn_key]
                            time_delta = current_time - old_time
                            if time_delta > 0:
                                port_dict['bytes_sent_rate'] = (bytes_sent - old_sent) / time_delta
                                port_dict['bytes_recv_rate'] = (bytes_recv - old_recv) / time_delta
                        
                        # Update cache
                        self._traffic_cache[conn_key] = (bytes_sent, bytes_recv, current_time)
                    elif conn_key:
                        # Connection exists but no traffic data yet - initialize cache
                        self._traffic_cache[conn_key] = (0, 0, current_time)
                    
                    ports.append(port_dict)
                    
                except (ValueError, IndexError, AttributeError) as e:
                    # Skip lines that can't be parsed
                    continue
                    
        except (OSError, subprocess.SubprocessError):
            pass
        
        # Clean up old cache entries (older than 60 seconds)
        cutoff_time = current_time - 60
        keys_to_remove = [
            key for key, (_, _, ts) in self._traffic_cache.items()
            if ts < cutoff_time
        ]
        for key in keys_to_remove:
            del self._traffic_cache[key]
        
        return ports
    
    def _parse_traffic_stats(self, output: str) -> Dict[Tuple[int, str, int, Optional[str], Optional[int]], Tuple[int, int]]:
        """Parse traffic statistics from ss -i output.
        
        Args:
            output: Output from 'ss -tunapi' command.
            
        Returns:
            Dictionary mapping connection keys to (bytes_sent, bytes_recv) tuples.
        """
        traffic_data: Dict[Tuple[int, str, int, Optional[str], Optional[int]], Tuple[int, int]] = {}
        
        # Parse ss -i output
        # Format includes lines like:
        # ESTAB 0 0 192.168.1.1:12345 192.168.1.2:80 users:(("process",pid=1234,fd=3)) 
        #     skmem:(r0,rb131072,t0,tb65536,f0,w0,o0,bl0,d0) ts sack cubic wscale:7,7 rto:204 rtt:0.5/0.5 ato:40 mss:1448 pmtu:1500 rcvmss:1448 advmss:1448 cwnd:10 bytes_sent:12345 bytes_acked:12000 bytes_received:54321 bytes_retrans:0 segs_out:100 segs_in:200
        
        current_conn = None
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('State'):
                continue
            
            # Check if this is a connection line (starts with state)
            parts = line.split()
            if len(parts) >= 5 and parts[0] in ['ESTAB', 'ESTABLISHED', 'LISTEN', 'TIME-WAIT', 'CLOSE-WAIT', 'FIN-WAIT-1', 'FIN-WAIT-2']:
                # This is a connection line - extract connection info
                try:
                    state = parts[0]
                    local_addr_port = parts[4]
                    remote_addr_port = parts[5] if len(parts) > 5 else None
                    
                    # Extract PID and process name
                    pid = None
                    name = None
                    process_match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                    if process_match:
                        name = process_match.group(1)
                        pid = int(process_match.group(2))
                    
                    if pid is None:
                        continue
                    
                    # Parse addresses (simplified - reuse logic from get_open_ports if needed)
                    local_addr, local_port = self._parse_addr_port(local_addr_port)
                    remote_addr, remote_port = self._parse_addr_port(remote_addr_port) if remote_addr_port and remote_addr_port != '*' else (None, None)
                    
                    if local_addr and local_port:
                        current_conn = (pid, local_addr, local_port, remote_addr, remote_port)
                except (ValueError, IndexError):
                    continue
            elif current_conn and ('bytes_sent:' in line or 'bytes_received:' in line or 'bytes_acked:' in line):
                # This line contains traffic statistics
                bytes_sent = 0
                bytes_recv = 0
                
                # Extract bytes_sent
                sent_match = re.search(r'bytes_sent:(\d+)', line)
                if sent_match:
                    bytes_sent = int(sent_match.group(1))
                
                # Extract bytes_received (or bytes_acked for sent data)
                recv_match = re.search(r'bytes_received:(\d+)', line)
                if recv_match:
                    bytes_recv = int(recv_match.group(1))
                
                if bytes_sent > 0 or bytes_recv > 0:
                    traffic_data[current_conn] = (bytes_sent, bytes_recv)
        
        return traffic_data
    
    def _parse_addr_port(self, addr_port: str) -> Tuple[Optional[str], Optional[int]]:
        """Parse address:port string.
        
        Args:
            addr_port: Address:port string (e.g., "127.0.0.1:8080" or "[::1]:8080").
            
        Returns:
            Tuple of (address, port) or (None, None) if parsing fails.
        """
        if not addr_port or addr_port == '*':
            return (None, None)
        
        if addr_port.startswith('['):
            # IPv6 with brackets: [::1]:8080
            bracket_end = addr_port.find(']')
            if bracket_end > 0 and bracket_end < len(addr_port) - 1:
                addr = addr_port[1:bracket_end]
                if addr_port[bracket_end + 1] == ':':
                    try:
                        port = int(addr_port[bracket_end + 2:])
                        return (addr, port)
                    except ValueError:
                        return (None, None)
        elif ':' in addr_port:
            # IPv4 or IPv6 without brackets
            if '::' in addr_port:
                # IPv6 without brackets
                parts = addr_port.rsplit(':', 1)
                if len(parts) == 2:
                    try:
                        port = int(parts[1])
                        return (parts[0], port)
                    except ValueError:
                        return (None, None)
            else:
                # IPv4
                try:
                    addr, port_str = addr_port.rsplit(':', 1)
                    port = int(port_str)
                    return (addr, port)
                except ValueError:
                    return (None, None)
        
        return (None, None)
    
    def get_ports_by_pid(self, pid: int) -> List[Dict[str, Any]]:
        """Get open ports for a specific process.
        
        Args:
            pid: Process ID to get ports for.
            
        Returns:
            List of port dictionaries (same format as get_open_ports).
        """
        all_ports = self.get_open_ports()
        return [p for p in all_ports if p.get('pid') == pid]

