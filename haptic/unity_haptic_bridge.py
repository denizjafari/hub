#!/usr/bin/env python3
"""
unity_haptic_bridge.py — Bridge between Unity/VR system and haptic controller

This module provides a bridge for Unity to communicate with the haptic system,
supporting real-time compensation detection and haptic feedback.
"""

import json
import time
import threading
from typing import Dict, List, Optional, Any
from enhanced_controller import HapticController
from enhanced_protocol import HapticSignalType


class UnityHapticBridge:
    """Bridge between Unity and the haptic feedback system."""
    
    def __init__(self, config_dir: str = "haptic/configs"):
        self.controller = HapticController(config_dir)
        self.compensation_thresholds = {
            "shoulder_elevation": 0.7,
            "trunk_lateral_flexion": 0.6,
            "arm_compensation": 0.8,
            "wrist_deviation": 0.5
        }
        self.movement_modules = {
            "shoulder_flexion": ["Haptic_01", "Haptic_02"],  # Deltoids
            "elbow_flexion": ["Haptic_03", "Haptic_04"],    # Forearms
            "trunk_movement": ["Haptic_05", "Haptic_06"],   # Scapulas
        }
        self.active_session = None
        self.session_data = []
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
    
    def start_exercise_session(self, exercise_name: str, target_muscles: List[str]):
        """Start a new exercise session."""
        self.active_session = {
            "exercise_name": exercise_name,
            "start_time": time.time(),
            "target_muscles": target_muscles,
            "compensation_count": 0,
            "movement_count": 0
        }
        self.session_data = []
        
        # Send initial calibration
        self.controller.calibrate_modules(self._get_all_modules())
        
        print(f"Started exercise session: {exercise_name}")
        return {"status": "started", "session_id": id(self.active_session)}
    
    def end_exercise_session(self):
        """End the current exercise session."""
        if not self.active_session:
            return {"status": "error", "message": "No active session"}
        
        self.active_session["end_time"] = time.time()
        duration = self.active_session["end_time"] - self.active_session["start_time"]
        
        # Stop all haptic feedback
        self.controller.stop_all_modules()
        
        session_summary = {
            "status": "completed",
            "duration_seconds": duration,
            "compensation_count": self.active_session["compensation_count"],
            "movement_count": self.active_session["movement_count"],
            "compensation_rate": (self.active_session["compensation_count"] / 
                                max(self.active_session["movement_count"], 1))
        }
        
        print(f"Exercise session completed: {session_summary}")
        self.active_session = None
        return session_summary
    
    def process_movement_data(self, movement_data: Dict[str, Any]):
        """Process movement data from Unity and trigger appropriate haptic feedback."""
        if not self.active_session:
            return {"status": "error", "message": "No active session"}
        
        # Extract movement parameters
        movement_type = movement_data.get("movement_type")
        joint_angles = movement_data.get("joint_angles", {})
        compensation_scores = movement_data.get("compensation_scores", {})
        
        # Check for compensatory movements
        compensation_detected = self._detect_compensation(compensation_scores)
        
        if compensation_detected:
            self._handle_compensation(compensation_detected)
        else:
            self._handle_normal_movement(movement_type, joint_angles)
        
        # Record session data
        self.session_data.append({
            "timestamp": time.time(),
            "movement_type": movement_type,
            "joint_angles": joint_angles,
            "compensation_scores": compensation_scores,
            "compensation_detected": bool(compensation_detected)
        })
        
        return {"status": "processed", "compensation_detected": bool(compensation_detected)}
    
    def _detect_compensation(self, compensation_scores: Dict[str, float]) -> Optional[Dict]:
        """Detect if compensatory movements are occurring."""
        detected_compensations = []
        
        for movement_type, score in compensation_scores.items():
            threshold = self.compensation_thresholds.get(movement_type, 0.5)
            if score > threshold:
                detected_compensations.append({
                    "type": movement_type,
                    "severity": score,
                    "threshold": threshold
                })
        
        if detected_compensations:
            return {
                "compensations": detected_compensations,
                "max_severity": max(c["severity"] for c in detected_compensations),
                "affected_modules": self._get_affected_modules(detected_compensations)
            }
        
        return None
    
    def _get_affected_modules(self, compensations: List[Dict]) -> List[str]:
        """Determine which modules should be activated based on compensations."""
        affected_modules = []
        
        for comp in compensations:
            comp_type = comp["type"]
            if "shoulder" in comp_type:
                affected_modules.extend(self.movement_modules["shoulder_flexion"])
            elif "elbow" in comp_type or "arm" in comp_type:
                affected_modules.extend(self.movement_modules["elbow_flexion"])
            elif "trunk" in comp_type:
                affected_modules.extend(self.movement_modules["trunk_movement"])
        
        return list(set(affected_modules))  # Remove duplicates
    
    def _handle_compensation(self, compensation_data: Dict):
        """Handle detected compensatory movement."""
        self.active_session["compensation_count"] += 1
        
        severity = compensation_data["max_severity"]
        affected_modules = compensation_data["affected_modules"]
        
        # Trigger sharp alarm signal
        self.controller.trigger_compensation_alarm(affected_modules, severity)
        
        print(f"Compensation detected: {compensation_data['compensations']}")
    
    def _handle_normal_movement(self, movement_type: str, joint_angles: Dict[str, float]):
        """Handle normal movement with gentle guidance signals."""
        self.active_session["movement_count"] += 1
        
        # Determine which modules to activate based on movement type
        target_modules = self.movement_modules.get(movement_type, [])
        
        if target_modules:
            # Send gentle queue tap signals
            intensity = 0.3 + (0.2 * (joint_angles.get("effort", 0.5)))  # Adjust intensity based on effort
            self.controller.queue_movement_signal(target_modules, intensity)
    
    def _get_all_modules(self) -> List[str]:
        """Get list of all configured modules."""
        return list(self.controller.modules.keys())
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                if self.active_session:
                    # Check system health
                    status = self.controller.get_system_status()
                    
                    # Alert if modules go offline
                    offline_modules = status["offline_modules"]
                    if offline_modules > 0:
                        print(f"Warning: {offline_modules} modules are offline")
                
                time.sleep(2.0)  # Check every 2 seconds
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status."""
        if not self.active_session:
            return {"status": "no_session"}
        
        return {
            "status": "active",
            "exercise_name": self.active_session["exercise_name"],
            "duration": time.time() - self.active_session["start_time"],
            "movement_count": self.active_session["movement_count"],
            "compensation_count": self.active_session["compensation_count"],
            "system_status": self.controller.get_system_status()
        }
    
    def send_custom_pattern(self, modules: List[str], pattern_type: str, 
                          duration_ms: int = 1000, intensity: float = 0.5):
        """Send custom haptic pattern to specified modules."""
        if pattern_type == "queue_tap":
            self.controller.queue_movement_signal(modules, intensity)
        elif pattern_type == "alarm_sharp":
            self.controller.trigger_compensation_alarm(modules, intensity)
        elif pattern_type == "wave":
            self.controller.execute_wave_pattern(modules, intensity)
        elif pattern_type == "sync":
            self.controller.execute_sync_pattern(modules, intensity)
        else:
            return {"status": "error", "message": f"Unknown pattern type: {pattern_type}"}
        
        return {"status": "sent", "modules": modules, "pattern": pattern_type}


# Example usage for Unity integration
if __name__ == "__main__":
    bridge = UnityHapticBridge()
    
    # Simulate Unity communication
    print("=== Unity Haptic Bridge Test ===")
    
    # Start exercise session
    session = bridge.start_exercise_session("shoulder_flexion", ["deltoids"])
    print(f"Session started: {session}")
    
    # Simulate normal movement
    print("\n--- Normal Movement ---")
    movement_data = {
        "movement_type": "shoulder_flexion",
        "joint_angles": {"shoulder": 45.0, "elbow": 90.0, "effort": 0.6},
        "compensation_scores": {"shoulder_elevation": 0.2, "trunk_lateral_flexion": 0.1}
    }
    result = bridge.process_movement_data(movement_data)
    print(f"Movement processed: {result}")
    
    time.sleep(1)
    
    # Simulate compensatory movement
    print("\n--- Compensatory Movement ---")
    compensation_data = {
        "movement_type": "shoulder_flexion",
        "joint_angles": {"shoulder": 60.0, "elbow": 90.0, "effort": 0.8},
        "compensation_scores": {"shoulder_elevation": 0.8, "trunk_lateral_flexion": 0.7}
    }
    result = bridge.process_movement_data(compensation_data)
    print(f"Movement processed: {result}")
    
    time.sleep(3)
    
    # End session
    print("\n--- Ending Session ---")
    summary = bridge.end_exercise_session()
    print(f"Session summary: {summary}")
