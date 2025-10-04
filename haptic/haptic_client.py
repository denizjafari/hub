#!/usr/bin/env python3
"""
haptic_client.py — Talk to XIAO-ESP32C3 haptic modules over Wi-Fi (UDP)

Enhanced version supporting multiple haptic modules with individual configurations.
Defaults are set from your ESP printout:
  IP:    192.168.86.239
  MASK:  255.255.255.0  -> broadcast 192.168.86.255
  PORT:  5005
"""
import argparse, json, socket, ipaddress, sys, time
import os
from haptic_manager import HapticManager

DEFAULT_IP   = "192.168.86.239"
DEFAULT_MASK = "255.255.255.0"
DEFAULT_PORT = 5005
DEFAULT_TOKEN = "change-me"   # <- must match your config.json on the module

def make_sock(broadcast=False, timeout=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if broadcast:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if timeout is not None:
        s.settimeout(timeout)
    return s

def calc_broadcast(ip=DEFAULT_IP, mask=DEFAULT_MASK):
    net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
    return str(net.broadcast_address)

def send_json(ip, port, payload, wait_reply=False, timeout=1.5, broadcast=False):
    data = json.dumps(payload).encode()
    s = make_sock(broadcast=broadcast, timeout=timeout if wait_reply else None)
    s.sendto(data, (ip, port))
    if not wait_reply:
        s.close()
        return None
    try:
        resp, addr = s.recvfrom(2048)
        s.close()
        return addr[0], resp.decode(errors="ignore")
    except socket.timeout:
        s.close()
        return None

def discover(port=DEFAULT_PORT, token=DEFAULT_TOKEN, mask=DEFAULT_MASK, ip=DEFAULT_IP, wait_s=1.5):
    """Broadcast 'ping' and collect all replies for wait_s seconds."""
    bcast = calc_broadcast(ip, mask)
    s = make_sock(broadcast=True, timeout=wait_s)
    msg = json.dumps({"cmd":"ping","token":token}).encode()
    s.sendto(msg, (bcast, port))
    s.settimeout(0.1)
    found = {}
    t0 = time.time()
    while time.time() - t0 < wait_s:
        try:
            resp, addr = s.recvfrom(2048)
            found[addr[0]] = resp.decode(errors="ignore")
        except socket.timeout:
            pass
    s.close()
    return bcast, found

def main():
    p = argparse.ArgumentParser(description="Control Wi-Fi haptic module(s) over UDP.")
    p.add_argument("--ip", default=DEFAULT_IP, help="ESP IP (or broadcast if using 'broadcast-*' cmds)")
    p.add_argument("--mask", default=DEFAULT_MASK, help="Subnet mask (for broadcast calc)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--token", default=DEFAULT_TOKEN)
    p.add_argument("--target", default=None, help='Optional device_id filter on the ESP (e.g., "Haptic_01")')
    sub = p.add_subparsers(dest="cmd", required=True)

    # Original commands
    s_ping = sub.add_parser("ping", help="Ping one module and print reply")
    s_buzz = sub.add_parser("buzz", help="Buzz one module")
    s_buzz.add_argument("--ms", type=int, default=2000)
    s_buzz.add_argument("--intensity", type=float, default=0.8)
    s_buzz.add_argument("--beep", action="store_true")

    s_stop = sub.add_parser("stop", help="Stop one module")

    s_bcast_ping = sub.add_parser("broadcast-ping", help="Ping all modules via broadcast and list replies")
    s_bcast_ping.add_argument("--wait", type=float, default=1.5)

    s_bcast_buzz = sub.add_parser("broadcast-buzz", help="Buzz all modules on the subnet")
    s_bcast_buzz.add_argument("--ms", type=int, default=1200)
    s_bcast_buzz.add_argument("--intensity", type=float, default=0.7)
    s_bcast_buzz.add_argument("--beep", action="store_true")

    # New multi-module commands
    s_discover = sub.add_parser("discover", help="Discover and map all haptic modules")
    s_discover.add_argument("--wait", type=float, default=3.0, help="Discovery wait time in seconds")

    s_list = sub.add_parser("list", help="List all configured modules and their status")

    s_buzz_multi = sub.add_parser("buzz-multi", help="Buzz multiple modules by device ID")
    s_buzz_multi.add_argument("devices", nargs="+", help="Device IDs to buzz (e.g., Haptic_01)")
    s_buzz_multi.add_argument("--ms", type=int, default=None, help="Duration in milliseconds")
    s_buzz_multi.add_argument("--intensity", type=float, default=None, help="Intensity (0.0-1.0)")
    s_buzz_multi.add_argument("--beep", action="store_true")

    s_buzz_all = sub.add_parser("buzz-all", help="Buzz all online modules")
    s_buzz_all.add_argument("--ms", type=int, default=1500)
    s_buzz_all.add_argument("--intensity", type=float, default=0.7)
    s_buzz_all.add_argument("--beep", action="store_true")

    s_stop_multi = sub.add_parser("stop-multi", help="Stop multiple modules by device ID")
    s_stop_multi.add_argument("devices", nargs="+", help="Device IDs to stop")

    s_stop_all = sub.add_parser("stop-all", help="Stop all online modules")

    s_status = sub.add_parser("status", help="Show detailed status of all modules")

    args = p.parse_args()

    # Initialize manager for multi-module commands
    manager = None
    if args.cmd in ["discover", "list", "buzz-multi", "buzz-all", "stop-multi", "stop-all", "status"]:
        try:
            manager = HapticManager(args.config_dir)
        except Exception as e:
            print(f"Error initializing haptic manager: {e}")
            sys.exit(1)

    # Original single-module commands
    if args.cmd == "ping":
        payload = {"cmd":"ping", "token":args.token}
        if args.target: payload["target"] = args.target
        r = send_json(args.ip, args.port, payload, wait_reply=True, timeout=2.0)
        if r:
            ip, txt = r
            print(f"Reply from {ip}: {txt}")
        else:
            print("No reply. Check IP/port/token and that the ESP is on your LAN.")
        return

    if args.cmd == "buzz":
        payload = {"cmd":"buzz","duration_ms":args.ms,"intensity":args.intensity,"token":args.token}
        if args.beep: payload["beep"] = True
        if args.target: payload["target"] = args.target
        send_json(args.ip, args.port, payload, wait_reply=False)
        print(f"Sent buzz to {args.ip}:{args.port}  ms={args.ms}  intensity={args.intensity}  beep={args.beep}")
        return

    if args.cmd == "stop":
        payload = {"cmd":"stop","token":args.token}
        if args.target: payload["target"] = args.target
        send_json(args.ip, args.port, payload, wait_reply=False)
        print(f"Sent stop to {args.ip}:{args.port}")
        return

    if args.cmd == "broadcast-ping":
        bcast, found = discover(port=args.port, token=args.token, mask=args.mask, ip=args.ip, wait_s=args.wait)
        if not found:
            print(f"No replies to broadcast ping on {bcast}:{args.port}.")
            sys.exit(1)
        print(f"Broadcast {bcast}:{args.port} replies:")
        for k,v in found.items():
            print(f"  {k} -> {v}")
        return

    if args.cmd == "broadcast-buzz":
        bcast = calc_broadcast(args.ip, args.mask)
        payload = {"cmd":"buzz","duration_ms":args.ms,"intensity":args.intensity,"token":args.token}
        if args.beep: payload["beep"] = True
        send_json(bcast, args.port, payload, wait_reply=False, broadcast=True)
        print(f"Broadcast buzz to {bcast}:{args.port}  ms={args.ms}  intensity={args.intensity}  beep={args.beep}")
        return

    # New multi-module commands
    if args.cmd == "discover":
        print("Discovering haptic modules...")
        manager.discover_modules(wait_time=args.wait)
        print("\nDiscovery complete!")
        manager.list_modules()
        return

    if args.cmd == "list":
        manager.list_modules()
        return

    if args.cmd == "buzz-multi":
        print(f"Buzzing modules: {', '.join(args.devices)}")
        for device_id in args.devices:
            success = manager.buzz_module(device_id, args.ms, args.intensity, args.beep)
            if success:
                module = manager.modules[device_id]
                print(f"  ✓ {device_id} ({module.location})")
            else:
                print(f"  ✗ {device_id} (failed or offline)")
        return

    if args.cmd == "buzz-all":
        manager.buzz_all_online(args.ms, args.intensity, args.beep)
        return

    if args.cmd == "stop-multi":
        print(f"Stopping modules: {', '.join(args.devices)}")
        for device_id in args.devices:
            success = manager.stop_module(device_id)
            if success:
                module = manager.modules[device_id]
                print(f"  ✓ {device_id} ({module.location})")
            else:
                print(f"  ✗ {device_id} (failed or offline)")
        return

    if args.cmd == "stop-all":
        manager.stop_all_online()
        return

    if args.cmd == "status":
        status = manager.get_status()
        print("\n=== Detailed Module Status ===")
        for device_id, info in status.items():
            print(f"\n{device_id}:")
            print(f"  Location: {info['location']}")
            print(f"  Description: {info['description']}")
            print(f"  IP: {info['ip'] or 'Not discovered'}")
            print(f"  Status: {'ONLINE' if info['is_online'] else 'OFFLINE'}")
            if info['last_seen']:
                print(f"  Last seen: {time.ctime(info['last_seen'])}")
            print(f"  Default intensity: {info['default_intensity']}")
            print(f"  Max intensity: {info['max_intensity']}")
            print(f"  Default duration: {info['default_duration_ms']}ms")
        return

if __name__ == "__main__":
    main()
