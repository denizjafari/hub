# main.py — XIAO-ESP32C3 Wi-Fi haptic (MicroPython v1.26)
import network, time, socket, ujson, machine

# ==== PINS per your schematic ====
MOTOR_PIN  = 2   # D0 -> GPIO2 (through 330Ω to 2N3904/2N2222 base)
BUZZER_PIN = 3   # D1 -> GPIO3 (active buzzer +)

PWM_FREQ   = 250  # 200–300 Hz typical for ERM motors

# ==== Load config ====
def load_cfg():
    try:
        with open('config.json') as f:
            return ujson.loads(f.read())
    except:
        return {
            "ssid": "Deniz",
            "password": "13711353",
            "udp_port": 5005,
            "device_id": "haptic01",
            "token": "change-me"
        }

cfg = load_cfg()
UDP_PORT  = int(cfg.get("udp_port", 5005))
DEVICE_ID = cfg.get("device_id", "haptic01")
TOKEN     = cfg.get("token", "change-me")

# ==== Compat for constants across firmware variants ====
try:
    STA_IF = network.WLAN.IF_STA
    AP_IF  = network.WLAN.IF_AP
except AttributeError:
    STA_IF = network.STA_IF
    AP_IF  = network.AP_IF

# ==== Hardware ====
pwm = machine.PWM(machine.Pin(MOTOR_PIN)); pwm.freq(PWM_FREQ); pwm.duty_u16(0)
buzzer = machine.Pin(BUZZER_PIN, machine.Pin.OUT); buzzer.value(0)

def set_intensity(x: float):
    # clamp 0..1 → duty 0..65535
    if x < 0: x = 0
    if x > 1: x = 1
    pwm.duty_u16(int(x * 65535))

def beep(ms=120):
    try:
        buzzer.value(1)
        time.sleep_ms(int(ms))
    finally:
        buzzer.value(0)

# ==== Wi-Fi helpers ====
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
        network.country('CA')  # set your country for RF rules
    except: pass
    sta = network.WLAN(STA_IF)
    if not sta.active(): sta.active(True)
    try:
        sta.disconnect()
    except: pass
    try:
        sta.connect(ssid, password)
    except OSError as e:
        print("connect() error:", e)  # e.g. OSError: Wifi Internal Error
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

wifi_scan_print()
sta = wifi_connect(cfg["ssid"], cfg["password"])
mode = "STA" if sta else "AP"
netif = sta if sta else start_ap("Haptic-" + DEVICE_ID)

# ==== UDP server ====
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", UDP_PORT))
sock.settimeout(0.05)
print("UDP listening on 0.0.0.0:{} ({})".format(UDP_PORT, mode))

active_until_ms = 0

def stop_vibe():
    global active_until_ms
    set_intensity(0.0)
    active_until_ms = 0

def start_vibe(duration_ms: int, intensity: float):
    global active_until_ms
    set_intensity(intensity)
    active_until_ms = time.ticks_add(time.ticks_ms(), max(0, int(duration_ms)))

def handle_packet(payload: bytes, src):
    try:
        msg = ujson.loads(payload)
    except Exception as e:
        print("bad JSON from", src, e); return
    if msg.get("token") != TOKEN:
        print("bad token from", src); return
    tgt = msg.get("target")
    if tgt and tgt != DEVICE_ID:
        return
    cmd = msg.get("cmd","")
    if cmd == "buzz":
        ms  = int(msg.get("duration_ms", 1000))
        inten = float(msg.get("intensity", 1.0))
        ms = 0 if ms < 0 else 10000 if ms > 10000 else ms
        inten = 0 if inten < 0 else 1 if inten > 1 else inten
        start_vibe(ms, inten)
        if msg.get("beep"): beep(120)
    elif cmd == "stop":
        stop_vibe()
    elif cmd == "ping":
        ip = netif.ifconfig()[0] if hasattr(netif,'ifconfig') else "0.0.0.0"
        resp = ujson.dumps({"id":DEVICE_ID,"ip":ip,"mode":mode,"ok":True})
        try: sock.sendto(resp.encode(), src)
        except: pass

# ==== Main loop ====
while True:
    try:
        data, src = sock.recvfrom(512)
        handle_packet(data, src)
    except OSError:
        pass
    if active_until_ms and time.ticks_diff(active_until_ms, time.ticks_ms()) <= 0:
        stop_vibe()
