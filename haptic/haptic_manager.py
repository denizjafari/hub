#!/usr/bin/env python3
"""
haptic_manager.py — Manager class for multiple haptic modules

This class provides a high-level interface to manage and control
multiple haptic modules with individual configurations.
"""

import json
import os
import socket
import ipaddress
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HapticModule:
    """Represents a single haptic module configuration."""
    device_id: str
    ip: str
    port: int
    token: str
    description: str
    default_intensity: float
    max_intensity: float
    default_duration_ms: int
    last_seen: Optional[float] = None
    is_online: bool = False


class HapticManager:
    """Manages multiple haptic modules with individual configurations."""
    
    def __init__(self, config_dir: str = "haptic/configs"):
        self.config_dir = config_dir
        self.modules: Dict[str, HapticModule] = {}
        self.discovered_modules: Dict[str, Tuple[str, str]] = {}  # device_id -> (ip, response)
        self.load_configurations()
    
    def load_configurations(self):
        """Load all haptic module configurations from the config directory."""
        if not os.path.exists(self.config_dir):
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")
        
        config_files = [f for f in os.listdir(self.config_dir) if f.endswith('.json')]
        
        for config_file in config_files:
            config_path = os.path.join(self.config_dir, config_file)
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                module = HapticModule(
                    device_id=config['device_id'],
                    ip="",  # Will be discovered
                    port=config['udp_port'],
                    token=config['token'],
                    description=config['description'],
                    default_intensity=config.get('default_intensity', 0.8),
                    max_intensity=config.get('max_intensity', 1.0),
                    default_duration_ms=config.get('default_duration_ms', 2000)
                )
                
                self.modules[module.device_id] = module
                print(f"Loaded configuration for {module.device_id}")
                
            except Exception as e:
                print(f"Error loading config {config_file}: {e}")
    
    def discover_modules(self, wait_time: float = 3.0, mask: str = "255.255.255.0") -> Dict[str, HapticModule]:
        """Discover all haptic modules on the network and map them to configurations."""
        if not self.modules:
            print("No module configurations loaded!")
            return {}
        
        # Use the first module's port for discovery (they should all use the same port)
        first_module = next(iter(self.modules.values()))
        port = first_module.port
        token = first_module.token
        
        # Calculate broadcast address
        # We'll try common network ranges
        broadcast_addresses = [
            "192.168.1.255",
            "192.168.0.255", 
            "192.168.86.255",
            "10.0.0.255"
        ]
        
        discovered = {}
        
        for bcast_ip in broadcast_addresses:
            try:
                bcast_discovered = self._discover_on_broadcast(bcast_ip, port, token, wait_time)
                discovered.update(bcast_discovered)
            except Exception as e:
                print(f"Discovery failed on {bcast_ip}: {e}")
                continue
        
        # Map discovered modules to configurations
        mapped_modules = {}
        for device_id, module in self.modules.items():
            # Check if we found this device_id in discovery
            if device_id in discovered:
                ip, response = discovered[device_id]
                module.ip = ip
                module.last_seen = time.time()
                module.is_online = True
                mapped_modules[device_id] = module
                print(f"✓ {device_id} ({module.location}) found at {ip}")
            else:
                module.is_online = False
                print(f"✗ {device_id} ({module.location}) not found")
        
        return mapped_modules
    
    def _discover_on_broadcast(self, bcast_ip: str, port: int, token: str, wait_time: float) -> Dict[str, Tuple[str, str]]:
        """Discover modules on a specific broadcast address."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Send ping to all modules
        msg = json.dumps({"cmd": "ping", "token": token}).encode()
        s.sendto(msg, (bcast_ip, port))
        
        # Collect responses
        s.settimeout(0.1)
        found = {}
        t0 = time.time()
        
        while time.time() - t0 < wait_time:
            try:
                resp, addr = s.recvfrom(2048)
                response_text = resp.decode(errors="ignore")
                
                # Try to parse the response to get device_id
                try:
                    response_data = json.loads(response_text)
                    device_id = response_data.get('device_id', 'UNKNOWN')
                    found[device_id] = (addr[0], response_text)
                except json.JSONDecodeError:
                    # If we can't parse JSON, use IP as device_id fallback
                    found[addr[0]] = (addr[0], response_text)
                    
            except socket.timeout:
                continue
        
        s.close()
        return found
    
    def send_command(self, device_id: str, command: str, **kwargs) -> bool:
        """Send a command to a specific haptic module."""
        if device_id not in self.modules:
            print(f"Unknown device: {device_id}")
            return False
        
        module = self.modules[device_id]
        if not module.is_online:
            print(f"Device {device_id} is not online")
            return False
        
        payload = {
            "cmd": command,
            "token": module.token,
            "target": device_id,
            **kwargs
        }
        
        try:
            data = json.dumps(payload).encode()
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.0)
            s.sendto(data, (module.ip, module.port))
            s.close()
            return True
        except Exception as e:
            print(f"Error sending command to {device_id}: {e}")
            return False
    
    def buzz_module(self, device_id: str, duration_ms: Optional[int] = None, 
                   intensity: Optional[float] = None, beep: bool = False) -> bool:
        """Send buzz command to a specific module."""
        module = self.modules.get(device_id)
        if not module:
            print(f"Unknown device: {device_id}")
            return False
        
        duration = duration_ms or module.default_duration_ms
        intensity_val = intensity or module.default_intensity
        
        return self.send_command(device_id, "buzz", 
                               duration_ms=duration, 
                               intensity=intensity_val, 
                               beep=beep)
    
    def stop_module(self, device_id: str) -> bool:
        """Stop a specific haptic module."""
        return self.send_command(device_id, "stop")
    
    def buzz_all_online(self, duration_ms: int = 1500, intensity: float = 0.7, beep: bool = False):
        """Send buzz command to all online modules."""
        online_modules = [m for m in self.modules.values() if m.is_online]
        
        if not online_modules:
            print("No online modules found")
            return
        
        print(f"Buzzing {len(online_modules)} modules...")
        for module in online_modules:
            success = self.buzz_module(module.device_id, duration_ms, intensity, beep)
            if success:
                print(f"  ✓ {module.device_id} ({module.location})")
            else:
                print(f"  ✗ {module.device_id} ({module.location})")
    
    def stop_all_online(self):
        """Stop all online haptic modules."""
        online_modules = [m for m in self.modules.values() if m.is_online]
        
        if not online_modules:
            print("No online modules found")
            return
        
        print(f"Stopping {len(online_modules)} modules...")
        for module in online_modules:
            success = self.stop_module(module.device_id)
            if success:
                print(f"  ✓ {module.device_id} ({module.location})")
            else:
                print(f"  ✗ {module.device_id} ({module.location})")
    
    def get_status(self) -> Dict[str, dict]:
        """Get status of all configured modules."""
        status = {}
        for device_id, module in self.modules.items():
            status[device_id] = {
                "description": module.description,
                "ip": module.ip,
                "is_online": module.is_online,
                "last_seen": module.last_seen,
                "default_intensity": module.default_intensity,
                "max_intensity": module.max_intensity,
                "default_duration_ms": module.default_duration_ms
            }
        return status
    
    def list_modules(self):
        """Print a formatted list of all modules and their status."""
        print("\n=== Haptic Modules Status ===")
        for device_id, module in self.modules.items():
            status = "ONLINE" if module.is_online else "OFFLINE"
            ip_info = f"({module.ip})" if module.ip else "(not discovered)"
            print(f"{device_id:12} | {module.location:15} | {status:7} {ip_info}")
        print()


if __name__ == "__main__":
    # Example usage
    manager = HapticManager()
    
    print("Discovering haptic modules...")
    manager.discover_modules()
    
    print("\nModule Status:")
    manager.list_modules()
    
    # Example: Buzz all online modules
    print("Testing buzz on all online modules...")
    manager.buzz_all_online(duration_ms=1000, intensity=0.5)
    time.sleep(2)
    manager.stop_all_online()
