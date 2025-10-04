import os
import time
import ximu3
import csv
import socket
import json
from datetime import datetime


class Connection:
    def __init__(self, connection_info, session_dir, unity_socket, device_index, quest_ip, quest_port):
        """
        connection_info: ximu3.ConnectionInfo object
        session_dir: Full path to the timestamped folder where CSV files should be created
        unity_socket: UDP socket to send data to Unity
        device_index: Unique index for this IMU device
        quest_ip: IP address of Meta Quest 3 headset
        quest_port: UDP port to send data to
        """

        self.__connection = ximu3.Connection(connection_info)
        if self.__connection.open() != ximu3.RESULT_OK:
            raise Exception(f"Unable to open {connection_info.to_string()}")

        ping_response = self.__connection.ping()
        if ping_response.result != ximu3.RESULT_OK:
            raise Exception(f"Ping failed for {connection_info.to_string()}")

        self.__prefix = f"{ping_response.device_name} {ping_response.serial_number} "
        device_name = ping_response.device_name.strip()
        serial = ping_response.serial_number.strip()
        
        # Store Unity communication parameters
        self.unity_socket = unity_socket
        self.device_index = device_index
        self.device_name = device_name
        self.serial_number = serial
        self.quest_ip = quest_ip
        self.quest_port = quest_port

        # Register built-in callbacks
        self.__connection.add_ahrs_status_callback(self.__ahrs_status_callback)
        self.__connection.add_temperature_callback(self.__temperature_callback)
        self.__connection.add_battery_callback(self.__battery_callback)
        self.__connection.add_rssi_callback(self.__rssi_callback)
        self.__connection.add_serial_accessory_callback(self.__serial_accessory_callback)
        self.__connection.add_notification_callback(self.__notification_callback)

        # Dictionaries to store CSV file handles and writers.
        self.csv_files = {}
        self.csv_writers = {}

        # One place to define all callback config
        self.callback_configs = {
            "inertial": {
                "header": ["device", "timestamp", "gyro_x [deg/s]", "gyro_y [deg/s]", "gyro_z [deg/s]",
                           "acc_x [g]", "acc_y [g]", "acc_z [g]"],
                "parser": self.parse_inertial,
                "register_method": "add_inertial_callback"
            },
            "magnetometer": {
                "header": ["device", "timestamp", "mag_x [a.u.]", "mag_y [a.u.]", "mag_z [a.u.]"],
                "parser": self.parse_magnetometer,
                "register_method": "add_magnetometer_callback"
            },
            "quaternion": {
                "header": ["device", "timestamp", "q0", "q1", "q2", "q3"],
                "parser": self.parse_quaternion,
                "register_method": "add_quaternion_callback"
            },
            "rotation_matrix": {
                "header": ["device", "timestamp", "R_xx", "R_xy", "R_xz",
                           "R_yx","R_yy","R_yz","R_zx","R_zy","R_zz"],
                "parser": self.parse_rotation,
                "register_method": "add_rotation_matrix_callback"
            },
            "euler_angles": {
                "header": ["device", "timestamp", "Roll [deg]", "Pitch [deg]", "Yaw [deg]"],
                "parser": self.parse_euler,
                "register_method": "add_euler_angles_callback"
            },
            "linear_acceleration": {
                "header": ["device", "timestamp", "q0", "q1", "q2", "q3",
                           "acc_x [g]", "acc_y [g]", "acc_z [g]"],
                "parser": self.parse_linear_acc,
                "register_method": "add_linear_acceleration_callback"
            },
            "earth_acceleration": {
                "header": ["device", "timestamp", "q0", "q1", "q2", "q3",
                           "E_acc_x [g]", "E_acc_y [g]", "E_acc_z [g]"],
                "parser": self.parse_earth_linear_acc,
                "register_method": "add_earth_acceleration_callback"
            },
            "high_g_accelerometer": {
                "header": ["device", "timestamp", "high-g_acc_x [g]",
                           "high-g_acc_y [g]", "high-g_acc_z [g]"],
                "parser": self.parse_high_g,
                "register_method": "add_high_g_accelerometer_callback"
            },
            "error": {
                "header": ["error_message"],
                "parser": self.parse_error,
                "register_method": "add_error_callback"
            }
        }

        # Create CSV files, register callbacks
        for cb_name, config in self.callback_configs.items():
            filename = f"{device_name}_{serial}_{cb_name}_log.csv"
            full_path = os.path.join(session_dir, filename)

            csv_file = open(full_path, "w", newline="")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(config["header"])

            self.csv_files[cb_name] = csv_file
            self.csv_writers[cb_name] = csv_writer

            print(f"Created CSV file for {cb_name} data: {full_path}")

            # Dynamically register the callback with the connection
            register_method = getattr(self.__connection, config["register_method"])
            register_method(lambda message, cb=cb_name: self.handle_callback(cb, message))

    def handle_callback(self, cb_name, message):
        """
        Generic callback handler: print the message with prefix, parse the data,
        and log it to the appropriate CSV file.
        """
        msg_str = message.to_string()
        print(self.__prefix + msg_str)
        row = self.callback_configs[cb_name]["parser"](message)
        if row is not None and cb_name in self.csv_writers:
            self.csv_writers[cb_name].writerow(row)
            self.csv_files[cb_name].flush()

    def parse_inertial(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 4:
            print("Unexpected inertial message format:", data_str)
            return None
        timestamp = parts[0]
        gyro_x, gyro_y, gyro_z = parts[2:7:2]
        acc_x, acc_y, acc_z = parts[8::2]
        device_name = self.__prefix.split()[0]
        return [device_name, timestamp, gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z]

    def parse_magnetometer(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 4:
            print("Unexpected magnetometer message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        mag_x, mag_y, mag_z = parts[2::2]
        return [device_name, timestamp, mag_x, mag_y, mag_z]

    def parse_quaternion(self, message):
        """
        Parse quaternion and send to Unity via UDP
        """
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 4:
            print("Unexpected quaternion message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        q0, q1, q2, q3 = parts[-4:]
        
        # Send quaternion data to Unity
        self.send_to_unity(float(q0), float(q1), float(q2), float(q3))
        
        return [device_name, timestamp, q0, q1, q2, q3]

    def send_to_unity(self, w, x, y, z):
        """
        Send quaternion data to Unity via UDP
        Unity uses (x, y, z, w) format
        """
        try:
            data = {
                "device_index": self.device_index,
                "device_name": self.device_name,
                "serial": self.serial_number,
                "quaternion": {
                    "x": x,
                    "y": y,
                    "z": z,
                    "w": w
                }
            }
            message = json.dumps(data).encode('utf-8')
            self.unity_socket.sendto(message, (self.quest_ip, self.quest_port))
        except Exception as e:
            print(f"Error sending to Unity: {e}")

    def parse_rotation(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 4:
            print("Unexpected rotation matrix message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        R_xx, R_xy, R_xz, R_yx, R_yy, R_yz, R_zx, R_zy, R_zz = parts[-9:]
        return [device_name, timestamp,
                R_xx, R_xy, R_xz,
                R_yx, R_yy, R_yz,
                R_zx, R_zy, R_zz]

    def parse_euler(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 3:
            print("Unexpected euler angles message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        roll, pitch, yaw = parts[1:]
        return [device_name, timestamp, roll, pitch, yaw]

    def parse_linear_acc(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 5:
            print("Unexpected linear_acc message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        q0, q1, q2, q3 = parts[1:5]
        x, y, z = parts[-3:]
        return [device_name, timestamp, q0, q1, q2, q3, x, y, z]

    def parse_earth_linear_acc(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 5:
            print("Unexpected earth_acc message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        q0, q1, q2, q3 = parts[1:5]
        x, y, z = parts[-3:]
        return [device_name, timestamp, q0, q1, q2, q3, x, y, z]

    def parse_high_g(self, message):
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 3:
            print("Unexpected high-g message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        x, y, z = parts[2::2]
        return [device_name, timestamp, x, y, z]

    def parse_error(self, message):
        return [message.to_string()]

    # Internal callbacks
    def __ahrs_status_callback(self, message):
        print("AHRS status callback invoked!")
        print(self.__prefix + message.to_string())

    def __temperature_callback(self, message):
        print("temp callback invoked!")
        print(self.__prefix + message.to_string())

    def __battery_callback(self, message):
        print("battery callback invoked!")
        print(self.__prefix + message.to_string())

    def __rssi_callback(self, message):
        print("RSSI callback invoked!")
        print(self.__prefix + message.to_string())

    def __serial_accessory_callback(self, message):
        print("Serial Access callback invoked!")
        print(self.__prefix + message.to_string())

    def __notification_callback(self, message):
        print("Notification callback invoked!")
        print(self.__prefix + message.to_string())

    def close(self):
        self.__connection.close()
        # Close all CSV files
        for cb_name, csv_file in self.csv_files.items():
            csv_file.close()
            print(f"{cb_name.capitalize()} CSV file closed.")

    def send_command(self, key, value=None):
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
        if not responses:
            raise Exception(f"No response to {command} for {self.__connection.get_info().to_string()}")
        else:
            print(self.__prefix + responses[0])


#
# Main script
#
if __name__ == "__main__":
    print("=" * 60)
    print("IMU to Meta Quest 3 - Real-Time Quaternion Streaming")
    print("=" * 60)
    
    # Get Quest 3 IP address from user
    print("\nTo find your Quest 3 IP address:")
    print("1. Put on your Quest 3 headset")
    print("2. Go to Settings > Wi-Fi")
    print("3. Click on your connected network")
    print("4. Look for 'IP Address' (e.g., 192.168.1.xxx)")
    print("\nMake sure your PC and Quest are on the SAME Wi-Fi network!\n")
    
    quest_ip = input("Enter your Quest 3 IP address: ").strip()
    quest_port = 5065
    
    print(f"\nTarget: {quest_ip}:{quest_port}")
    print("Press Enter to continue or Ctrl+C to abort...")
    input()
    
    # 1) Create DataLogger parent directory if not present
    parent_dir = "DataLogger"
    os.makedirs(parent_dir, exist_ok=True)

    # 2) Create a timestamped folder for this session
    session_dir_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir_path = os.path.join(parent_dir, session_dir_name)
    os.makedirs(session_dir_path, exist_ok=True)

    # 3) Create UDP socket for Unity communication
    unity_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP socket created. Sending to Quest 3 at {quest_ip}:{quest_port}")

    # Detect available UDP connections
    print("\nSearching for IMU devices...")
    detected_messages = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
    connections = [Connection(m.to_udp_connection_info(), session_dir_path, unity_socket, idx, quest_ip, quest_port) 
                   for idx, m in enumerate(detected_messages)]

    if not connections:
        raise Exception("No UDP connections available")

    print(f"\n{'=' * 60}")
    print(f"Connected to {len(connections)} IMU device(s)")
    for idx, conn in enumerate(connections):
        print(f"  Device {idx}: {conn.device_name} (Serial: {conn.serial_number})")
    print(f"{'=' * 60}")

    # Example commands to each connection
    for connection in connections:
        connection.send_command("udpDataMessagesEnabled", True)
        connection.send_command("inertialMessageRateDivisor", 8)

    print("\n🚀 Streaming data to Quest 3...")
    print("   Make sure your Unity app is running on the Quest!")
    print("   Press Ctrl+C to stop\n")
    
    try:
        # Keep streaming until user interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping data stream...")

    # Close each connection properly
    for connection in connections:
        connection.close()
    
    unity_socket.close()
    print("✅ All connections closed.")
    print(f"📁 Data saved to: {session_dir_path}")