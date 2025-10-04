#!/usr/bin/env python3
"""
enhanced_protocol.py — Enhanced communication protocol for haptic system

This module defines the improved communication protocol supporting:
- Two distinct buzz signal types (queuing vs alarming)
- Message queuing and prioritization
- Health monitoring and diagnostics
- Synchronized multi-module patterns
"""

import json
import time
import enum
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from enum import Enum


class HapticSignalType(Enum):
    """Types of haptic signals supported by the system."""
    QUEUE_TAP = "queue_tap"          # Slow, low intensity tapping for movement queuing
    ALARM_SHARP = "alarm_sharp"      # High frequency, sharp, continuous for compensation warnings
    BUZZ_STANDARD = "buzz_standard"  # Standard buzz (existing functionality)
    PATTERN_WAVE = "pattern_wave"    # Wave pattern across multiple modules
    PATTERN_SYNC = "pattern_sync"    # Synchronized pattern across modules


class MessagePriority(Enum):
    """Message priority levels for command queuing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class HapticCommand:
    """Enhanced haptic command structure."""
    cmd: str
    signal_type: HapticSignalType
    duration_ms: int
    intensity: float
    priority: MessagePriority = MessagePriority.NORMAL
    target_device: Optional[str] = None
    pattern_id: Optional[str] = None
    sync_group: Optional[str] = None
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary for JSON serialization."""
        data = asdict(self)
        data['signal_type'] = self.signal_type.value
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HapticCommand':
        """Create command from dictionary."""
        data['signal_type'] = HapticSignalType(data['signal_type'])
        data['priority'] = MessagePriority(data['priority'])
        return cls(**data)


@dataclass
class ModuleStatus:
    """Module status and health information."""
    device_id: str
    ip: str
    port: int
    is_online: bool
    last_seen: float
    battery_level: Optional[float] = None
    temperature: Optional[float] = None
    signal_strength: Optional[int] = None
    active_commands: int = 0
    error_count: int = 0
    firmware_version: Optional[str] = None


class EnhancedHapticProtocol:
    """Enhanced protocol handler for haptic communication."""
    
    def __init__(self):
        self.command_queue: List[HapticCommand] = []
        self.module_status: Dict[str, ModuleStatus] = {}
        self.signal_patterns: Dict[str, Dict] = {
            "queue_tap": {
                "frequency_hz": 2.0,
                "duty_cycle": 0.3,
                "intensity_range": (0.1, 0.4),
                "description": "Gentle tapping for movement queuing"
            },
            "alarm_sharp": {
                "frequency_hz": 15.0,
                "duty_cycle": 0.8,
                "intensity_range": (0.7, 1.0),
                "description": "Sharp, urgent signal for compensation warnings"
            },
            "buzz_standard": {
                "frequency_hz": 8.0,
                "duty_cycle": 0.6,
                "intensity_range": (0.3, 0.8),
                "description": "Standard haptic feedback"
            }
        }
    
    def create_queue_tap(self, duration_ms: int = 500, intensity: float = 0.3, 
                        target_device: Optional[str] = None) -> HapticCommand:
        """Create a gentle tap signal for movement queuing."""
        return HapticCommand(
            cmd="pattern",
            signal_type=HapticSignalType.QUEUE_TAP,
            duration_ms=duration_ms,
            intensity=min(max(intensity, 0.1), 0.4),
            priority=MessagePriority.NORMAL,
            target_device=target_device,
            metadata={"pattern_type": "tap", "tap_interval_ms": 500}
        )
    
    def create_alarm_sharp(self, duration_ms: int = 2000, intensity: float = 0.9,
                          target_device: Optional[str] = None) -> HapticCommand:
        """Create a sharp, urgent signal for compensation warnings."""
        return HapticCommand(
            cmd="pattern",
            signal_type=HapticSignalType.ALARM_SHARP,
            duration_ms=duration_ms,
            intensity=min(max(intensity, 0.7), 1.0),
            priority=MessagePriority.HIGH,
            target_device=target_device,
            metadata={"pattern_type": "sharp", "burst_interval_ms": 100}
        )
    
    def create_wave_pattern(self, devices: List[str], duration_per_device: int = 300,
                           intensity: float = 0.6, delay_between: int = 100) -> List[HapticCommand]:
        """Create a wave pattern across multiple devices."""
        commands = []
        for i, device_id in enumerate(devices):
            cmd = HapticCommand(
                cmd="pattern",
                signal_type=HapticSignalType.PATTERN_WAVE,
                duration_ms=duration_per_device,
                intensity=intensity,
                priority=MessagePriority.NORMAL,
                target_device=device_id,
                pattern_id=f"wave_{int(time.time())}",
                sync_group="wave",
                metadata={
                    "wave_position": i,
                    "total_devices": len(devices),
                    "delay_offset_ms": i * delay_between
                }
            )
            commands.append(cmd)
        return commands
    
    def create_sync_pattern(self, devices: List[str], duration_ms: int = 1000,
                           intensity: float = 0.7) -> List[HapticCommand]:
        """Create synchronized pattern across multiple devices."""
        sync_id = f"sync_{int(time.time())}"
        commands = []
        for device_id in devices:
            cmd = HapticCommand(
                cmd="pattern",
                signal_type=HapticSignalType.PATTERN_SYNC,
                duration_ms=duration_ms,
                intensity=intensity,
                priority=MessagePriority.HIGH,
                target_device=device_id,
                pattern_id=sync_id,
                sync_group="sync",
                metadata={"sync_start_time": time.time()}
            )
            commands.append(cmd)
        return commands
    
    def queue_command(self, command: HapticCommand):
        """Add command to priority queue."""
        self.command_queue.append(command)
        self.command_queue.sort(key=lambda x: (x.priority.value, x.timestamp), reverse=True)
    
    def get_next_command(self) -> Optional[HapticCommand]:
        """Get the next command from the queue."""
        if self.command_queue:
            return self.command_queue.pop(0)
        return None
    
    def generate_pattern_sequence(self, signal_type: HapticSignalType, 
                                 duration_ms: int, intensity: float) -> List[Dict]:
        """Generate the actual pattern sequence for a signal type."""
        pattern_config = self.signal_patterns.get(signal_type.value, {})
        
        if signal_type == HapticSignalType.QUEUE_TAP:
            # Gentle tapping: short bursts with pauses
            tap_duration = 100
            pause_duration = 400
            taps = []
            current_time = 0
            
            while current_time < duration_ms:
                taps.append({
                    "time_offset_ms": current_time,
                    "duration_ms": tap_duration,
                    "intensity": intensity,
                    "frequency_hz": pattern_config.get("frequency_hz", 2.0)
                })
                current_time += tap_duration + pause_duration
            return taps
            
        elif signal_type == HapticSignalType.ALARM_SHARP:
            # Sharp alarm: rapid bursts with high intensity
            burst_duration = 80
            pause_duration = 20
            bursts = []
            current_time = 0
            
            while current_time < duration_ms:
                bursts.append({
                    "time_offset_ms": current_time,
                    "duration_ms": burst_duration,
                    "intensity": intensity,
                    "frequency_hz": pattern_config.get("frequency_hz", 15.0)
                })
                current_time += burst_duration + pause_duration
            return bursts
            
        else:
            # Standard buzz
            return [{
                "time_offset_ms": 0,
                "duration_ms": duration_ms,
                "intensity": intensity,
                "frequency_hz": pattern_config.get("frequency_hz", 8.0)
            }]


class MessageSerializer:
    """Handles serialization/deserialization of protocol messages."""
    
    @staticmethod
    def serialize_command(command: HapticCommand) -> str:
        """Serialize command to JSON string."""
        return json.dumps(command.to_dict())
    
    @staticmethod
    def deserialize_command(data: str) -> HapticCommand:
        """Deserialize command from JSON string."""
        return HapticCommand.from_dict(json.loads(data))
    
    @staticmethod
    def serialize_status(status: ModuleStatus) -> str:
        """Serialize module status to JSON string."""
        return json.dumps(asdict(status))
    
    @staticmethod
    def deserialize_status(data: str) -> ModuleStatus:
        """Deserialize module status from JSON string."""
        return ModuleStatus(**json.loads(data))


# Example usage and testing
if __name__ == "__main__":
    protocol = EnhancedHapticProtocol()
    
    # Create different signal types
    queue_tap = protocol.create_queue_tap(duration_ms=1000, intensity=0.3)
    alarm_sharp = protocol.create_alarm_sharp(duration_ms=2000, intensity=0.9)
    
    # Create wave pattern
    devices = ["Haptic_01", "Haptic_02", "Haptic_03"]
    wave_commands = protocol.create_wave_pattern(devices, duration_per_device=300)
    
    # Generate pattern sequences
    tap_pattern = protocol.generate_pattern_sequence(HapticSignalType.QUEUE_TAP, 1000, 0.3)
    alarm_pattern = protocol.generate_pattern_sequence(HapticSignalType.ALARM_SHARP, 2000, 0.9)
    
    print("Queue Tap Pattern:")
    for step in tap_pattern:
        print(f"  {step}")
    
    print("\nAlarm Sharp Pattern:")
    for step in alarm_pattern:
        print(f"  {step}")
