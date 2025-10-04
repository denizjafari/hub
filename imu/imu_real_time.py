import os
import time
import ximu3
import csv
from datetime import datetime
from collections import deque


class IMUConnection:
    def __init__(self, connection_info, enable_csv_logging=False, session_dir=None):
        """
        Lightweight IMU connection for real-time data reading on Raspberry Pi
        
        Args:
            connection_info: ximu3.ConnectionInfo object
            enable_csv_logging: If True, saves data to CSV files
            session_dir: Directory for CSV files (only used if enable_csv_logging=True)
        """
        self.__connection = ximu3.Connection(connection_info)
        if self.__connection.open() != ximu3.RESULT_OK:
            raise Exception(f"Unable to open {connection_info.to_string()}")

        ping_response = self.__connection.ping()
        if ping_response.result != ximu3.RESULT_OK:
            raise Exception(f"Ping failed for {connection_info.to_string()}")

        self.device_name = ping_response.device_name.strip()
        self.serial_number = ping_response.serial_number.strip()
        self.__prefix = f"{self.device_name} {self.serial_number} "
        
        # Data storage for real-time access
        self.latest_data = {
            "inertial": None,
            "magnetometer": None,
            "quaternion": None,
            "euler_angles": None,
            "temperature": None,
            "battery": None
        }
        
        # Optional: Keep recent history (last N samples)
        self.data_history = {
            "inertial": deque(maxlen=100),
            "quaternion": deque(maxlen=100),
            "euler_angles": deque(maxlen=100)
        }
        
        # CSV logging setup (optional)
        self.enable_csv_logging = enable_csv_logging
        self.csv_files = {}
        self.csv_writers = {}
        
        if self.enable_csv_logging and session_dir:
            self._setup_csv_logging(session_dir)
        
        # Register callbacks for data streams
        self._register_callbacks()
        
        print(f"✅ Connected to {self.device_name} (Serial: {self.serial_number})")

    def _setup_csv_logging(self, session_dir):
        """Setup CSV files for logging (optional)"""
        csv_configs = {
            "inertial": ["timestamp", "gyro_x", "gyro_y", "gyro_z", "acc_x", "acc_y", "acc_z"],
            "quaternion": ["timestamp", "q0", "q1", "q2", "q3"],
            "euler_angles": ["timestamp", "roll", "pitch", "yaw"],
            "magnetometer": ["timestamp", "mag_x", "mag_y", "mag_z"]
        }
        
        for data_type, header in csv_configs.items():
            filename = f"{self.device_name}_{self.serial_number}_{data_type}.csv"
            full_path = os.path.join(session_dir, filename)
            
            csv_file = open(full_path, "w", newline="")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(header)
            
            self.csv_files[data_type] = csv_file
            self.csv_writers[data_type] = csv_writer

    def _register_callbacks(self):
        """Register callbacks for different data types"""
        self.__connection.add_inertial_callback(self._inertial_callback)
        self.__connection.add_magnetometer_callback(self._magnetometer_callback)
        self.__connection.add_quaternion_callback(self._quaternion_callback)
        self.__connection.add_euler_angles_callback(self._euler_callback)
        self.__connection.add_temperature_callback(self._temperature_callback)
        self.__connection.add_battery_callback(self._battery_callback)

    def _inertial_callback(self, message):
        """Process inertial data (gyroscope + accelerometer)"""
        data_str = message.to_string()
        parts = data_str.split()
        
        if len(parts) >= 13:
            data = {
                "timestamp": parts[0],
                "gyro_x": float(parts[2]),
                "gyro_y": float(parts[4]),
                "gyro_z": float(parts[6]),
                "acc_x": float(parts[8]),
                "acc_y": float(parts[10]),
                "acc_z": float(parts[12])
            }
            
            self.latest_data["inertial"] = data
            self.data_history["inertial"].append(data)
            
            if self.enable_csv_logging and "inertial" in self.csv_writers:
                row = [data["timestamp"], data["gyro_x"], data["gyro_y"], data["gyro_z"],
                       data["acc_x"], data["acc_y"], data["acc_z"]]
                self.csv_writers["inertial"].writerow(row)

    def _magnetometer_callback(self, message):
        """Process magnetometer data"""
        data_str = message.to_string()
        parts = data_str.split()
        
        if len(parts) >= 7:
            data = {
                "timestamp": parts[0],
                "mag_x": float(parts[2]),
                "mag_y": float(parts[4]),
                "mag_z": float(parts[6])
            }
            
            self.latest_data["magnetometer"] = data
            
            if self.enable_csv_logging and "magnetometer" in self.csv_writers:
                row = [data["timestamp"], data["mag_x"], data["mag_y"], data["mag_z"]]
                self.csv_writers["magnetometer"].writerow(row)

    def _quaternion_callback(self, message):
        """Process quaternion orientation data"""
        data_str = message.to_string()
        parts = data_str.split()
        
        if len(parts) >= 4:
            q0, q1, q2, q3 = parts[-4:]
            data = {
                "timestamp": parts[0],
                "q0": float(q0),
                "q1": float(q1),
                "q2": float(q2),
                "q3": float(q3)
            }
            
            self.latest_data["quaternion"] = data
            self.data_history["quaternion"].append(data)
            
            if self.enable_csv_logging and "quaternion" in self.csv_writers:
                row = [data["timestamp"], data["q0"], data["q1"], data["q2"], data["q3"]]
                self.csv_writers["quaternion"].writerow(row)

    def _euler_callback(self, message):
        """Process Euler angles (roll, pitch, yaw)"""
        data_str = message.to_string()
        parts = data_str.split()
        
        if len(parts) >= 4:
            data = {
                "timestamp": parts[0],
                "roll": float(parts[1]),
                "pitch": float(parts[2]),
                "yaw": float(parts[3])
            }
            
            self.latest_data["euler_angles"] = data
            self.data_history["euler_angles"].append(data)
            
            if self.enable_csv_logging and "euler_angles" in self.csv_writers:
                row = [data["timestamp"], data["roll"], data["pitch"], data["yaw"]]
                self.csv_writers["euler_angles"].writerow(row)

    def _temperature_callback(self, message):
        """Process temperature data"""
        data_str = message.to_string()
        self.latest_data["temperature"] = data_str

    def _battery_callback(self, message):
        """Process battery data"""
        data_str = message.to_string()
        self.latest_data["battery"] = data_str

    def get_latest_data(self, data_type=None):
        """
        Get the most recent data
        
        Args:
            data_type: Specific type ('inertial', 'quaternion', etc.) or None for all
        
        Returns:
            Latest data dictionary or specific data type
        """
        if data_type:
            return self.latest_data.get(data_type)
        return self.latest_data

    def get_data_history(self, data_type):
        """Get historical data buffer for a specific type"""
        return list(self.data_history.get(data_type, []))

    def print_status(self):
        """Print current sensor readings"""
        print(f"\n{'='*60}")
        print(f"Device: {self.device_name} ({self.serial_number})")
        print(f"{'='*60}")
        
        if self.latest_data["euler_angles"]:
            euler = self.latest_data["euler_angles"]
            print(f"Orientation (Euler):")
            print(f"  Roll:  {euler['roll']:7.2f}°")
            print(f"  Pitch: {euler['pitch']:7.2f}°")
            print(f"  Yaw:   {euler['yaw']:7.2f}°")
        
        if self.latest_data["inertial"]:
            inertial = self.latest_data["inertial"]
            print(f"Gyroscope (deg/s):")
            print(f"  X: {inertial['gyro_x']:7.2f}  Y: {inertial['gyro_y']:7.2f}  Z: {inertial['gyro_z']:7.2f}")
            print(f"Accelerometer (g):")
            print(f"  X: {inertial['acc_x']:7.2f}  Y: {inertial['acc_y']:7.2f}  Z: {inertial['acc_z']:7.2f}")
        
        if self.latest_data["battery"]:
            print(f"Battery: {self.latest_data['battery']}")
        
        if self.latest_data["temperature"]:
            print(f"Temperature: {self.latest_data['temperature']}")

    def send_command(self, key, value=None):
        """Send command to IMU device"""
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
            print(f"{self.__prefix}{responses[0]}")
        return responses

    def close(self):
        """Close connection and cleanup"""
        self.__connection.close()
        
        if self.enable_csv_logging:
            for csv_file in self.csv_files.values():
                csv_file.close()
        
        print(f"❌ Disconnected from {self.device_name}")


def main():
    """Main function to run IMU data reader"""
    print("="*60)
    print("IMU Real-Time Data Reader for Raspberry Pi")
    print("="*60)
    
    # Configuration
    ENABLE_CSV_LOGGING = input("\nEnable CSV logging? (y/n): ").lower().strip() == 'y'
    
    session_dir = None
    if ENABLE_CSV_LOGGING:
        parent_dir = "DataLogger"
        os.makedirs(parent_dir, exist_ok=True)
        session_dir_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_dir = os.path.join(parent_dir, session_dir_name)
        os.makedirs(session_dir, exist_ok=True)
        print(f"📁 Logging to: {session_dir}")
    
    # Discover IMU devices
    print("\n🔍 Searching for IMU devices...")
    detected_messages = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
    
    if not detected_messages:
        print("❌ No IMU devices found!")
        return
    
    # Connect to all detected devices
    connections = []
    for idx, msg in enumerate(detected_messages):
        try:
            conn = IMUConnection(
                msg.to_udp_connection_info(),
                enable_csv_logging=ENABLE_CSV_LOGGING,
                session_dir=session_dir
            )
            connections.append(conn)
        except Exception as e:
            print(f"❌ Failed to connect to device {idx}: {e}")
    
    if not connections:
        print("❌ No successful connections!")
        return
    
    print(f"\n✅ Connected to {len(connections)} device(s)")
    
    # Configure devices
    for conn in connections:
        conn.send_command("udpDataMessagesEnabled", True)
        conn.send_command("inertialMessageRateDivisor", 8)  # Adjust rate as needed
    
    print("\n🚀 Streaming data... Press Ctrl+C to stop\n")
    
    try:
        # Real-time monitoring loop
        while True:
            time.sleep(2)  # Update interval
            
            # Print status for each device
            for conn in connections:
                conn.print_status()
            
            # You can also access data programmatically:
            for conn in connections:
                quat = conn.get_latest_data("quaternion")
                if quat:
                    print(f"Device {conn.device_name} quaternion: {quat}")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping data stream...")
    
    # Cleanup
    for conn in connections:
        conn.close()
    
    if ENABLE_CSV_LOGGING:
        print(f"\n📁 Data saved to: {session_dir}")
    
    print("✅ Done!")


if __name__ == "__main__":
    main()