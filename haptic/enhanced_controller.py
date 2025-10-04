#!/usr/bin/env python3
"""
enhanced_controller.py — Enhanced Raspberry Pi haptic controller

This module provides advanced control capabilities for the haptic system:
- Intelligent pattern generation and sequencing
- Real-time compensation detection and response
- Synchronized multi-module coordination
- Health monitoring and diagnostics
"""

import json
import socket
import time
import threading
import queue
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enhanced_protocol import (
    HapticCommand, HapticSignalType, MessagePriority, 
    EnhancedHapticProtocol, MessageSerializer
)


@dataclass
class CompensationEvent:
    """Represents a detected compensatory movement event."""
    timestamp: float
    severity: float  # 0.0 to 1.0
    affected_modules: List[str]
    movement_type: str
    confidence: float


class HapticController:
    """Enhanced controller for managing haptic feedback system."""
    
    def __init__(self, config_dir: str = "haptic/configs"):
        self.protocol = EnhancedHapticProtocol()
        self.serializer = MessageSerializer()
        self.config_dir = config_dir
        
        # Module management
        self.modules: Dict[str, Dict] = {}
        self.module_status: Dict[str, Dict] = {}
        self.active_patterns: Dict[str, str] = {}
        
        # Communication
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.command_queue = queue.PriorityQueue()
        self.response_queue = queue.Queue()
        
        # Monitoring and diagnostics
        self.compensation_events: List[CompensationEvent] = []
        self.performance_metrics: Dict[str, Any] = {
            "total_commands_sent": 0,
            "successful_responses": 0,
            "failed_commands": 0,
            "average_response_time": 0.0
        }
        
        # Load module configurations
        self._load_module_configs()
        
        # Start background threads
        self._start_background_threads()
    
    def _load_module_configs(self):
        """Load module configurations from config directory."""
        import os
        import glob
        
        config_files = glob.glob(os.path.join(self.config_dir, "*.json"))
        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                device_id = config['device_id']
                self.modules[device_id] = config
                print(f"Loaded config for {device_id}")
            except Exception as e:
                print(f"Error loading config {config_file}: {e}")
    
    def _start_background_threads(self):
        """Start background threads for communication and monitoring."""
        # Command sender thread
        self.command_thread = threading.Thread(target=self._command_sender_loop, daemon=True)
        self.command_thread.start()
        
        # Response listener thread
        self.response_thread = threading.Thread(target=self._response_listener_loop, daemon=True)
        self.response_thread.start()
        
        # Health monitor thread
        self.health_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self.health_thread.start()
    
    def _command_sender_loop(self):
        """Background thread for sending commands."""
        while True:
            try:
                priority, command = self.command_queue.get(timeout=1.0)
                self._send_command(command)
                self.performance_metrics["total_commands_sent"] += 1
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in command sender: {e}")
                self.performance_metrics["failed_commands"] += 1
    
    def _response_listener_loop(self):
        """Background thread for listening to module responses."""
        self.socket.bind(("0.0.0.0", 5006))  # Listen on different port
        self.socket.settimeout(1.0)
        
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                response = json.loads(data.decode())
                self._handle_response(response, addr)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error in response listener: {e}")
    
    def _health_monitor_loop(self):
        """Background thread for health monitoring."""
        while True:
            try:
                self._update_module_health()
                time.sleep(5.0)  # Check every 5 seconds
            except Exception as e:
                print(f"Error in health monitor: {e}")
                time.sleep(1.0)
    
    def _send_command(self, command: HapticCommand):
        """Send a command to the target module."""
        if not command.target_device:
            print("No target device specified")
            return
        
        if command.target_device not in self.modules:
            print(f"Unknown device: {command.target_device}")
            return
        
        module_config = self.modules[command.target_device]
        target_ip = module_config.get('ip', '192.168.1.100')  # Default IP
        target_port = module_config.get('udp_port', 5005)
        
        # Create message
        message = {
            "cmd": "pattern",
            "signal_type": command.signal_type.value,
            "duration_ms": command.duration_ms,
            "intensity": command.intensity,
            "target": command.target_device,
            "token": module_config.get('token', 'change-me'),
            "priority": command.priority.value,
            "timestamp": command.timestamp
        }
        
        # Add pattern sequence if available
        if hasattr(command, 'metadata') and command.metadata:
            message.update(command.metadata)
        
        try:
            data = json.dumps(message).encode()
            self.socket.sendto(data, (target_ip, target_port))
            print(f"Sent command to {command.target_device}: {command.signal_type.value}")
        except Exception as e:
            print(f"Failed to send command to {command.target_device}: {e}")
            self.performance_metrics["failed_commands"] += 1
    
    def _handle_response(self, response: Dict, addr: Tuple[str, int]):
        """Handle response from a module."""
        device_id = response.get('id', 'unknown')
        self.module_status[device_id] = response
        self.performance_metrics["successful_responses"] += 1
        
        print(f"Response from {device_id}: {response.get('status', 'unknown')}")
    
    def _update_module_health(self):
        """Update module health status."""
        current_time = time.time()
        for device_id, status in self.module_status.items():
            last_seen = status.get('last_seen', 0)
            if current_time - last_seen > 30:  # 30 second timeout
                status['is_online'] = False
            else:
                status['is_online'] = True
    
    def queue_movement_signal(self, target_modules: List[str], intensity: float = 0.3):
        """Queue gentle tap signals for movement guidance."""
        for device_id in target_modules:
            if device_id in self.modules:
                command = self.protocol.create_queue_tap(
                    duration_ms=500,
                    intensity=intensity,
                    target_device=device_id
                )
                self.command_queue.put((command.priority.value, command))
    
    def trigger_compensation_alarm(self, affected_modules: List[str], severity: float = 0.9):
        """Trigger sharp alarm signals for compensatory movements."""
        # Create compensation event
        event = CompensationEvent(
            timestamp=time.time(),
            severity=severity,
            affected_modules=affected_modules,
            movement_type="compensation",
            confidence=0.8
        )
        self.compensation_events.append(event)
        
        # Send alarm signals
        for device_id in affected_modules:
            if device_id in self.modules:
                command = self.protocol.create_alarm_sharp(
                    duration_ms=2000,
                    intensity=severity,
                    target_device=device_id
                )
                self.command_queue.put((command.priority.value, command))
    
    def execute_wave_pattern(self, module_sequence: List[str], intensity: float = 0.6):
        """Execute a wave pattern across modules."""
        commands = self.protocol.create_wave_pattern(
            devices=module_sequence,
            duration_per_device=300,
            intensity=intensity,
            delay_between=100
        )
        
        for command in commands:
            self.command_queue.put((command.priority.value, command))
    
    def execute_sync_pattern(self, modules: List[str], intensity: float = 0.7):
        """Execute synchronized pattern across modules."""
        commands = self.protocol.create_sync_pattern(
            devices=modules,
            duration_ms=1000,
            intensity=intensity
        )
        
        for command in commands:
            self.command_queue.put((command.priority.value, command))
    
    def stop_all_modules(self):
        """Stop all active patterns on all modules."""
        for device_id in self.modules.keys():
            if device_id in self.module_status and self.module_status[device_id].get('is_online'):
                message = {
                    "cmd": "stop",
                    "target": device_id,
                    "token": self.modules[device_id].get('token', 'change-me')
                }
                try:
                    target_ip = self.modules[device_id].get('ip', '192.168.1.100')
                    target_port = self.modules[device_id].get('udp_port', 5005)
                    data = json.dumps(message).encode()
                    self.socket.sendto(data, (target_ip, target_port))
                except Exception as e:
                    print(f"Failed to stop {device_id}: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        online_modules = sum(1 for status in self.module_status.values() 
                           if status.get('is_online', False))
        total_modules = len(self.modules)
        
        return {
            "total_modules": total_modules,
            "online_modules": online_modules,
            "offline_modules": total_modules - online_modules,
            "active_patterns": len(self.active_patterns),
            "compensation_events": len(self.compensation_events),
            "performance_metrics": self.performance_metrics,
            "module_status": self.module_status
        }
    
    def calibrate_modules(self, modules: List[str]):
        """Perform calibration sequence on specified modules."""
        print(f"Starting calibration for modules: {modules}")
        
        # Step 1: Gentle test signal
        for device_id in modules:
            command = self.protocol.create_queue_tap(
                duration_ms=200,
                intensity=0.2,
                target_device=device_id
            )
            self.command_queue.put((command.priority.value, command))
        
        time.sleep(0.5)
        
        # Step 2: Standard test signal
        for device_id in modules:
            command = HapticCommand(
                cmd="pattern",
                signal_type=HapticSignalType.BUZZ_STANDARD,
                duration_ms=300,
                intensity=0.5,
                priority=MessagePriority.NORMAL,
                target_device=device_id
            )
            self.command_queue.put((command.priority.value, command))
        
        time.sleep(0.5)
        
        # Step 3: Stop all
        self.stop_all_modules()
        
        print("Calibration sequence completed")


# Example usage and testing
if __name__ == "__main__":
    controller = HapticController()
    
    # Wait for modules to come online
    print("Waiting for modules to come online...")
    time.sleep(3)
    
    # Test basic functionality
    print("\n=== Testing Movement Queue Signals ===")
    controller.queue_movement_signal(["Haptic_01", "Haptic_02"], intensity=0.3)
    time.sleep(2)
    
    print("\n=== Testing Compensation Alarm ===")
    controller.trigger_compensation_alarm(["Haptic_03", "Haptic_04"], severity=0.9)
    time.sleep(3)
    
    print("\n=== Testing Wave Pattern ===")
    controller.execute_wave_pattern(["Haptic_01", "Haptic_02", "Haptic_03"], intensity=0.6)
    time.sleep(4)
    
    print("\n=== Testing Synchronized Pattern ===")
    controller.execute_sync_pattern(["Haptic_04", "Haptic_05", "Haptic_06"], intensity=0.7)
    time.sleep(2)
    
    # Show system status
    print("\n=== System Status ===")
    status = controller.get_system_status()
    print(json.dumps(status, indent=2))
    
    # Cleanup
    controller.stop_all_modules()
    print("\nAll modules stopped.")
