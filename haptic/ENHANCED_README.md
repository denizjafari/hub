# Enhanced Haptic Feedback System v2.0

## 🚀 **System Overview**

The Enhanced Haptic Feedback System is a sophisticated multi-module haptic control system designed for rehabilitation and movement training applications. It supports real-time compensation detection and provides two distinct types of haptic feedback:

- **Queue Tap Signals**: Gentle, low-intensity tapping for movement guidance
- **Alarm Sharp Signals**: High-frequency, sharp signals for compensatory movement warnings


### **1. Enhanced Communication Protocol**
- **Message Prioritization**: Commands are queued by priority (Low, Normal, High, Critical)
- **Pattern Sequences**: Complex haptic patterns with precise timing
- **Health Monitoring**: Real-time module status and diagnostics
- **Synchronized Control**: Multi-module coordination with precise timing

### **2. Advanced Signal Types**

#### **Queue Tap Signals** (Movement Guidance)
```python
# Gentle tapping for movement queuing
frequency: 2.0 Hz
intensity: 0.1 - 0.4
pattern: Short bursts with pauses
use_case: Guiding correct movement patterns
```

#### **Alarm Sharp Signals** (Compensation Warnings)
```python
# Sharp, urgent signals for compensation warnings
frequency: 15.0 Hz
intensity: 0.7 - 1.0
pattern: Rapid bursts with high intensity
use_case: Alerting against compensatory movements
```

### **3. Intelligent Compensation Detection**
- **Real-time Analysis**: Continuous monitoring of joint angles and movement patterns
- **Threshold-based Detection**: Configurable thresholds for different movement types
- **Severity Mapping**: Graduated response based on compensation severity
- **Multi-module Response**: Coordinated haptic feedback across affected areas

## 📁 **File Structure**

```
haptic/
├── enhanced_protocol.py          # Enhanced communication protocol
├── enhanced_main.py              # Enhanced ESP32 firmware
├── enhanced_controller.py        # Raspberry Pi brain controller
├── unity_haptic_bridge.py        # Unity/VR integration bridge
├── enhanced_config.json          # System configuration
├── configs/                      # Individual module configs
│   ├── haptic_01.json           # Module 1 (Right Deltoid)
│   ├── haptic_02.json           # Module 2 (Left Deltoid)
│   ├── haptic_03.json           # Module 3 (Right Forearm)
│   ├── haptic_04.json           # Module 4 (Left Forearm)
│   ├── haptic_05.json           # Module 5 (Right Scapula)
│   └── haptic_06.json           # Module 6 (Left Scapula)
├── haptic_manager.py             # Module management system
├── haptic_client.py              # Command-line interface
└── ENHANCED_README.md            # This documentation
```

## 🔧 **Hardware Requirements**

### **ESP32 Modules (XIAO-ESP32C3)**
- **Motor Driver**: ERM/LRA haptic motor with 2N3904/2N2222 transistor
- **Pins**:
  - GPIO2: Motor control (PWM)
  - GPIO3: Buzzer (optional)
  - GPIO8: Status LED

### **Raspberry Pi Brain**
- **Network**: Wi-Fi 6/6E capable
- **Processing**: Real-time pattern generation and compensation detection
- **Communication**: UDP sockets for low-latency control

## 🚀 **Quick Start Guide**

### **1. Setup Module Configurations**
```bash
# Update each module's config.json with unique device IDs
# haptic_01.json -> device_id: "Haptic_01"
# haptic_02.json -> device_id: "Haptic_02"
# ... etc
```

### **2. Flash Enhanced Firmware**
```bash
# Upload enhanced_main.py to each ESP32 module
# Ensure each module has its corresponding config.json
```

### **3. Start the Controller**
```python
from enhanced_controller import HapticController

controller = HapticController()
# Controller will automatically discover and manage modules
```

### **4. Unity Integration**
```python
from unity_haptic_bridge import UnityHapticBridge

bridge = UnityHapticBridge()
session = bridge.start_exercise_session("shoulder_flexion", ["deltoids"])

# Process movement data from Unity
movement_data = {
    "movement_type": "shoulder_flexion",
    "joint_angles": {"shoulder": 45.0, "elbow": 90.0},
    "compensation_scores": {"shoulder_elevation": 0.2}
}
bridge.process_movement_data(movement_data)
```

## 📊 **Advanced Features**

### **1. Real-time Compensation Detection**

The system continuously monitors movement patterns and detects compensatory movements:

```python
compensation_thresholds = {
    "shoulder_elevation": 0.7,
    "trunk_lateral_flexion": 0.6,
    "arm_compensation": 0.8
}

# When compensation is detected:
# 1. Severity is calculated (0.0 - 1.0)
# 2. Affected modules are identified
# 3. Sharp alarm signals are triggered
# 4. Event is logged for analysis
```

### **2. Pattern Generation**

The system can generate complex haptic patterns:

```python
# Wave pattern across modules
controller.execute_wave_pattern(
    modules=["Haptic_01", "Haptic_02", "Haptic_03"],
    intensity=0.6,
    delay_between=100  # ms
)

# Synchronized pattern
controller.execute_sync_pattern(
    modules=["Haptic_04", "Haptic_05", "Haptic_06"],
    intensity=0.7
)
```

### **3. Health Monitoring**

Continuous monitoring of module health:

```python
status = controller.get_system_status()
print(f"Online modules: {status['online_modules']}")
print(f"Performance metrics: {status['performance_metrics']}")
```

## 🎮 **Unity Integration**

### **Movement Data Processing**
```python
# Unity sends movement data to the bridge
movement_data = {
    "movement_type": "shoulder_flexion",
    "joint_angles": {
        "shoulder": 45.0,
        "elbow": 90.0,
        "effort": 0.6
    },
    "compensation_scores": {
        "shoulder_elevation": 0.2,
        "trunk_lateral_flexion": 0.1
    }
}

result = bridge.process_movement_data(movement_data)
```

### **Session Management**
```python
# Start exercise session
session = bridge.start_exercise_session(
    exercise_name="shoulder_flexion",
    target_muscles=["deltoids"]
)

# End session and get summary
summary = bridge.end_exercise_session()
# Returns: duration, compensation_count, movement_count, etc.
```

## 🔧 **Configuration**

### **Signal Pattern Configuration**
```json
{
  "signal_patterns": {
    "queue_tap": {
      "frequency_hz": 2.0,
      "duty_cycle": 0.3,
      "intensity_range": [0.1, 0.4]
    },
    "alarm_sharp": {
      "frequency_hz": 15.0,
      "duty_cycle": 0.8,
      "intensity_range": [0.7, 1.0]
    }
  }
}
```

### **Compensation Detection Settings**
```json
{
  "compensation_detection": {
    "shoulder_elevation": {
      "threshold": 0.7,
      "affected_modules": ["Haptic_01", "Haptic_02"]
    }
  }
}
```

## 📈 **Performance Metrics**

The system tracks comprehensive performance metrics:

- **Command Success Rate**: Percentage of successfully delivered commands
- **Response Times**: Average module response times
- **Compensation Events**: Number and severity of detected compensations
- **Module Health**: Online/offline status and error counts
- **Session Analytics**: Movement counts, duration, and effectiveness

## 🔍 **Troubleshooting**

### **Common Issues**

1. **Modules Not Responding**
   ```bash
   # Check network connectivity
   python haptic_client.py discover --wait 5.0
   
   # Verify module status
   python haptic_client.py status
   ```

2. **Compensation Detection Not Working**
   ```python
   # Check thresholds in enhanced_config.json
   # Verify movement data format from Unity
   # Check compensation_scores are within expected ranges
   ```

3. **Pattern Execution Issues**
   ```python
   # Verify module firmware version (should be 2.0.0+)
   # Check pattern configuration in enhanced_config.json
   # Monitor system logs for errors
   ```

### **Debug Commands**
```bash
# Test individual modules
python haptic_client.py buzz-multi Haptic_01 --ms 1000 --intensity 0.5

# Test compensation alarm
python enhanced_controller.py --test-compensation

# Monitor system status
python enhanced_controller.py --monitor
```

## 🚀 **Future Enhancements**

### **Planned Features**
1. **Machine Learning Integration**: Adaptive threshold adjustment based on user performance
2. **Biometric Integration**: Heart rate and muscle activity monitoring
3. **Advanced Patterns**: Custom pattern designer for therapists
4. **Cloud Analytics**: Remote monitoring and data analysis
5. **Mobile App**: Therapist control interface

### **API Extensions**
- REST API for external system integration
- WebSocket support for real-time web interfaces
- MQTT integration for IoT ecosystem connectivity

## 📚 **API Reference**

### **HapticController Methods**
- `queue_movement_signal(modules, intensity)` - Send gentle guidance signals
- `trigger_compensation_alarm(modules, severity)` - Send sharp alarm signals
- `execute_wave_pattern(modules, intensity)` - Execute wave patterns
- `execute_sync_pattern(modules, intensity)` - Execute synchronized patterns
- `stop_all_modules()` - Stop all active patterns
- `get_system_status()` - Get comprehensive system status

### **UnityHapticBridge Methods**
- `start_exercise_session(name, muscles)` - Start new exercise session
- `process_movement_data(data)` - Process movement data and trigger feedback
- `end_exercise_session()` - End session and get summary
- `get_session_status()` - Get current session status

## 🤝 **Contributing**

To contribute to the Enhanced Haptic System:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests and documentation
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 **Support**

For technical support and questions:
- Create an issue in the repository
- Contact the development team
- Check the troubleshooting guide

---

**Version**: 2.0.0  
**Last Updated**: 2024  
**Compatibility**: Python 3.10+, MicroPython 1.26+, Unity 2022+
