import time
import ximu3
import socket
import json
from datetime import datetime

class QuaternionStreamer:
    def __init__(self, connection_info, device_index, quest_ip, quest_port):
        # Open connection
        self.__connection = ximu3.Connection(connection_info)
        if self.__connection.open() != ximu3.RESULT_OK:
            raise Exception(f"Unable to open {connection_info.to_string()}")
        
        # Verify connection
        ping_response = self.__connection.ping()
        if ping_response.result != ximu3.RESULT_OK:
            raise Exception(f"Ping failed")
        
        # Store device info
        self.device_name = ping_response.device_name.strip()
        self.serial_number = ping_response.serial_number.strip()
        self.device_index = device_index
        
        # UDP setup
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.quest_address = (quest_ip, quest_port)
        
        # Register only quaternion callback
        self.__connection.add_quaternion_callback(self.__quaternion_callback)
        
        print(f"Connected: {self.device_name} ({self.serial_number})")
    
    def __quaternion_callback(self, message):
        """Parse and send quaternion data"""
        parts = message.to_string().split()
        if len(parts) >= 4:
            q0, q1, q2, q3 = map(float, parts[-4:])
            self.__send_to_unity(q0, q1, q2, q3)
    
    def __send_to_unity(self, w, x, y, z):
        """Send quaternion to Unity"""
        try:
            data = {
                "device_index": self.device_index,
                "device_name": self.device_name,
                "quaternion": {"x": x, "y": y, "z": z, "w": w}
            }
            message = json.dumps(data).encode('utf-8')
            self.socket.sendto(message, self.quest_address)
        except Exception as e:
            print(f"UDP error: {e}")
    
    def send_command(self, key, value=None):
        """Send configuration commands to IMU"""
        if value is None:
            value = "null"
        elif isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, str):
            value = f'"{value}"'
        else:
            value = str(value)
        
        command = f'{{"{key}":{value}}}'
        responses = self.__connection.send_commands([command], 2, 500)
        if responses:
            print(f"Command response: {responses[0]}")
    
    def close(self):
        self.__connection.close()
        self.socket.close()

if __name__ == "__main__":
    # Get Quest IP
    quest_ip = input("Enter Quest 3 IP address: ").strip()
    quest_port = 5065
    
    # Detect IMUs
    print("Detecting IMUs...")
    messages = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
    
    if not messages:
        raise Exception("No IMUs detected")
    
    # Connect to all detected IMUs
    streamers = []
    for idx, msg in enumerate(messages):
        streamer = QuaternionStreamer(
            msg.to_udp_connection_info(), 
            idx, 
            quest_ip, 
            quest_port
        )
        streamer.send_command("udpDataMessagesEnabled", True)
        streamer.send_command("quaternionMessageRateDivisor", 4)  # Adjust rate as needed
        streamers.append(streamer)
    
    print(f"\n✅ Streaming from {len(streamers)} IMU(s) to {quest_ip}:{quest_port}")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
    finally:
        for streamer in streamers:
            streamer.close()
        print("✅ Done")