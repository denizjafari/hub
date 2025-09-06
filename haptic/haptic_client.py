#!/usr/bin/env python3
"""
haptic_client.py — Talk to XIAO-ESP32C3 haptic modules over Wi-Fi (UDP)

Defaults are set from your ESP printout:
  IP:    192.168.86.239
  MASK:  255.255.255.0  -> broadcast 192.168.86.255
  PORT:  5005
"""
import argparse, json, socket, ipaddress, sys, time

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
    p.add_argument("--target", default=None, help='Optional device_id filter on the ESP (e.g., "RHIP")')
    sub = p.add_subparsers(dest="cmd", required=True)

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

    args = p.parse_args()

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

if __name__ == "__main__":
    main()
