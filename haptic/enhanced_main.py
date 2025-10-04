# enhanced_main.py — Enhanced XIAO-ESP32C3 firmware with pattern support
import network, time, socket, ujson, machine, _thread
from collections import deque

# ==== HARDWARE PINS ====
MOTOR_PIN  = 2   # D0 -> GPIO2 (through 330Ω to 2N3904/2N2222 base)
BUZZER_PIN = 3   # D1 -> GPIO3 (active buzzer +)
LED_PIN    = 8   # D8 -> GPIO8 (status LED)

# ==== PATTERN CONFIGURATION ====
PATTERN_TYPES = {
    "queue_tap": {
        "frequency_hz": 2.0,
        "duty_cycle": 0.3,
        "burst_duration_ms": 100,
        "pause_duration_ms": 400
    },
    "alarm_sharp": {
        "frequency_hz": 15.0,
        "duty_cycle": 0.8,
        "burst_duration_ms": 80,
        "pause_duration_ms": 20
    },
    "buzz_standard": {
        "frequency_hz": 8.0,
        "duty_cycle": 0.6,
        "burst_duration_ms": 0,  # Continuous
        "pause_duration_ms": 0
    }
}

# ==== LOAD CONFIG ====
def load_cfg():
    try:
        with open('config.json') as f:
            return ujson.loads(f.read())
    except:
        return {
            "ssid": "Deniz",
            "password": "13711353",
            "udp_port": 5005,
            "device_id": "Haptic_01",
            "token": "change-me"
        }

cfg = load_cfg()
UDP_PORT  = int(cfg.get("udp_port", 5005))
DEVICE_ID = cfg.get("device_id", "Haptic_01")
TOKEN     = cfg.get("token", "change-me")

# ==== HARDWARE INITIALIZATION ====
pwm = machine.PWM(machine.Pin(MOTOR_PIN))
pwm.freq(250)  # Default frequency
pwm.duty_u16(0)

buzzer = machine.Pin(BUZZER_PIN, machine.Pin.OUT)
buzzer.value(0)

led = machine.Pin(LED_PIN, machine.Pin.OUT)
led.value(0)

# ==== PATTERN EXECUTION SYSTEM ====
class PatternExecutor:
    def __init__(self):
        self.active_pattern = None
        self.pattern_thread = None
        self.should_stop = False
        self.current_intensity = 0.0
        
    def set_intensity(self, intensity: float):
        """Set motor intensity with proper bounds checking."""
        if intensity < 0: intensity = 0
        if intensity > 1: intensity = 1
        self.current_intensity = intensity
        pwm.duty_u16(int(intensity * 65535))
    
    def stop(self):
        """Stop current pattern and motor."""
        self.should_stop = True
        self.set_intensity(0.0)
        if self.pattern_thread:
            _thread.exit()
    
    def execute_pattern(self, pattern_type: str, duration_ms: int, intensity: float):
        """Execute a haptic pattern."""
        if self.pattern_thread:
            self.stop()
            time.sleep_ms(50)  # Allow thread to exit
        
        self.should_stop = False
        pattern_config = PATTERN_TYPES.get(pattern_type, PATTERN_TYPES["buzz_standard"])
        
        def pattern_worker():
            start_time = time.ticks_ms()
            pattern_start = time.ticks_ms()
            
            while not self.should_stop and time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
                if pattern_type == "queue_tap":
                    # Gentle tapping pattern
                    self.set_intensity(intensity)
                    time.sleep_ms(pattern_config["burst_duration_ms"])
                    self.set_intensity(0.0)
                    time.sleep_ms(pattern_config["pause_duration_ms"])
                    
                elif pattern_type == "alarm_sharp":
                    # Sharp alarm pattern
                    self.set_intensity(intensity)
                    time.sleep_ms(pattern_config["burst_duration_ms"])
                    self.set_intensity(0.0)
                    time.sleep_ms(pattern_config["pause_duration_ms"])
                    
                elif pattern_type == "buzz_standard":
                    # Standard continuous buzz
                    self.set_intensity(intensity)
                    time.sleep_ms(duration_ms)
                    break
                
                # Check for early termination
                if self.should_stop:
                    break
            
            # Ensure motor is stopped
            self.set_intensity(0.0)
        
        self.pattern_thread = _thread.start_new_thread(pattern_worker, ())
    
    def execute_pattern_sequence(self, sequence: list, intensity: float):
        """Execute a complex pattern sequence."""
        if self.pattern_thread:
            self.stop()
            time.sleep_ms(50)
        
        self.should_stop = False
        
        def sequence_worker():
            for step in sequence:
                if self.should_stop:
                    break
                
                # Wait for the specified time offset
                time.sleep_ms(step.get("time_offset_ms", 0))
                
                # Execute the pattern step
                step_duration = step.get("duration_ms", 100)
                step_intensity = step.get("intensity", intensity)
                step_frequency = step.get("frequency_hz", 8.0)
                
                # Set PWM frequency if specified
                pwm.freq(int(step_frequency * 1000))  # Convert Hz to period
                
                # Execute the step
                self.set_intensity(step_intensity)
                time.sleep_ms(step_duration)
                
                if self.should_stop:
                    break
            
            # Reset to default frequency and stop
            pwm.freq(250)
            self.set_intensity(0.0)
        
        self.pattern_thread = _thread.start_new_thread(sequence_worker, ())

# Global pattern executor
executor = PatternExecutor()

# ==== STATUS MONITORING ====
class StatusMonitor:
    def __init__(self):
        self.error_count = 0
        self.last_heartbeat = time.ticks_ms()
        self.active_commands = 0
        self.battery_level = 100  # Placeholder - implement actual battery monitoring
        
    def get_status(self) -> dict:
        """Get current module status."""
        return {
            "device_id": DEVICE_ID,
            "ip": self.get_ip_address(),
            "port": UDP_PORT,
            "is_online": True,
            "last_seen": time.time(),
            "battery_level": self.battery_level,
            "temperature": 25.0,  # Placeholder - implement temperature monitoring
            "signal_strength": self.get_signal_strength(),
            "active_commands": self.active_commands,
            "error_count": self.error_count,
            "firmware_version": "2.0.0"
        }
    
    def get_ip_address(self) -> str:
        """Get current IP address."""
        try:
            if hasattr(netif, 'ifconfig'):
                return netif.ifconfig()[0]
        except:
            pass
        return "0.0.0.0"
    
    def get_signal_strength(self) -> int:
        """Get Wi-Fi signal strength."""
        try:
            if hasattr(netif, 'status') and hasattr(netif, 'scan'):
                # This is a simplified implementation
                return -50  # Placeholder
        except:
            pass
        return -100

status_monitor = StatusMonitor()

# ==== WI-FI SETUP (same as before) ====
try:
    STA_IF = network.WLAN.IF_STA
    AP_IF  = network.WLAN.IF_AP
except AttributeError:
    STA_IF = network.STA_IF
    AP_IF  = network.AP_IF

def wifi_scan_print():
    sta = network.WLAN(STA_IF); sta.active(True)
    try:
        nets = sta.scan()
        print("=== 2.4GHz scan ===")
        for ssid, bssid, chan, rssi, auth, hidden in nets[:12]:
            print("{:>2} {:>3}dBm a{:d} {}".format(chan, rssi, auth, ssid.decode()))
        print("===================")
    except Exception as e:
        print("scan fail:", e)

def wifi_connect(ssid, password, timeout_s=25):
    try:
        network.country('CA')
    except: pass
    sta = network.WLAN(STA_IF)
    if not sta.active(): sta.active(True)
    try:
        sta.disconnect()
    except: pass
    try:
        sta.connect(ssid, password)
    except OSError as e:
        print("connect() error:", e)
        return None
    t0 = time.ticks_ms()
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_s*1000:
            print("Wi-Fi timeout")
            return None
        time.sleep_ms(250)
    return sta

def start_ap(essid, password="12345678"):
    ap = network.WLAN(AP_IF)
    ap.active(True)
    ap.config(essid=essid, password=password, authmode=network.AUTH_WPA_WPA2_PSK)
    print("SoftAP:", essid, ap.ifconfig()[0])
    return ap

# ==== NETWORK SETUP ====
wifi_scan_print()
sta = wifi_connect(cfg["ssid"], cfg["password"])
mode = "STA" if sta else "AP"
netif = sta if sta else start_ap("Haptic-" + DEVICE_ID)

# ==== UDP SERVER ====
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", UDP_PORT))
sock.settimeout(0.05)
print("Enhanced UDP listening on 0.0.0.0:{} ({})".format(UDP_PORT, mode))

# ==== MESSAGE HANDLING ====
def handle_packet(payload: bytes, src):
    try:
        msg = ujson.loads(payload)
    except Exception as e:
        print("bad JSON from", src, e)
        status_monitor.error_count += 1
        return
    
    if msg.get("token") != TOKEN:
        print("bad token from", src)
        return
    
    tgt = msg.get("target")
    if tgt and tgt != DEVICE_ID:
        return
    
    cmd = msg.get("cmd", "")
    
    if cmd == "pattern":
        # New enhanced pattern command
        pattern_type = msg.get("signal_type", "buzz_standard")
        duration_ms = int(msg.get("duration_ms", 1000))
        intensity = float(msg.get("intensity", 0.5))
        
        # Validate parameters
        duration_ms = max(0, min(duration_ms, 10000))  # Max 10 seconds
        intensity = max(0.0, min(intensity, 1.0))
        
        print(f"Executing pattern: {pattern_type}, duration: {duration_ms}ms, intensity: {intensity}")
        
        # Check if it's a sequence or simple pattern
        if "sequence" in msg:
            # Execute pattern sequence
            sequence = msg["sequence"]
            executor.execute_pattern_sequence(sequence, intensity)
        else:
            # Execute simple pattern
            executor.execute_pattern(pattern_type, duration_ms, intensity)
        
        status_monitor.active_commands += 1
        
        # Send acknowledgment
        resp = ujson.dumps({
            "id": DEVICE_ID,
            "cmd": "pattern_ack",
            "pattern_type": pattern_type,
            "status": "executing"
        })
        try:
            sock.sendto(resp.encode(), src)
        except:
            pass
    
    elif cmd == "buzz":
        # Legacy buzz command (for backward compatibility)
        duration_ms = int(msg.get("duration_ms", 1000))
        intensity = float(msg.get("intensity", 0.5))
        
        duration_ms = max(0, min(duration_ms, 10000))
        intensity = max(0.0, min(intensity, 1.0))
        
        executor.execute_pattern("buzz_standard", duration_ms, intensity)
        status_monitor.active_commands += 1
        
        if msg.get("beep"):
            buzzer.value(1)
            time.sleep_ms(120)
            buzzer.value(0)
    
    elif cmd == "stop":
        executor.stop()
        status_monitor.active_commands = max(0, status_monitor.active_commands - 1)
    
    elif cmd == "ping":
        # Enhanced ping with status information
        status = status_monitor.get_status()
        resp = ujson.dumps(status)
        try:
            sock.sendto(resp.encode(), src)
        except:
            pass
    
    elif cmd == "status":
        # Return detailed status
        status = status_monitor.get_status()
        resp = ujson.dumps(status)
        try:
            sock.sendto(resp.encode(), src)
        except:
            pass
    
    elif cmd == "heartbeat":
        # Update heartbeat timestamp
        status_monitor.last_heartbeat = time.ticks_ms()
        led.value(1)
        time.sleep_ms(50)
        led.value(0)

# ==== MAIN LOOP ====
print("Enhanced haptic module started:", DEVICE_ID)
print("Supported patterns:", list(PATTERN_TYPES.keys()))

while True:
    try:
        data, src = sock.recvfrom(512)
        handle_packet(data, src)
    except OSError:
        pass
    
    # Status LED blinking
    if time.ticks_ms() % 2000 < 100:
        led.value(1)
    else:
        led.value(0)
    
    # Small delay to prevent busy waiting
    time.sleep_ms(10)
