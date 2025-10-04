from haptic_manager import HapticManager

manager = HapticManager()               # loads configs from haptic/configs
manager.discover_modules(wait_time=2.5) # find devices

# One device
manager.buzz_module("haptic_01", duration_ms=800, intensity=0.55, beep=True)

# All online devices
manager.buzz_all_online(duration_ms=1200, intensity=0.6)
manager.stop_all_online()