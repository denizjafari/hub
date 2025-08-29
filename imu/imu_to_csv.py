import os
import time
import ximu3
import csv
from datetime import datetime


class Connection:
    def __init__(self, connection_info, session_dir):
        """
        connection_info: ximu3.ConnectionInfo object
        session_dir: Full path to the timestamped folder where CSV files should be created
        """

        self.__connection = ximu3.Connection(connection_info)
        if self.__connection.open() != ximu3.RESULT_OK:
            raise Exception(f"Unable to open {connection_info.to_string()}")

        ping_response = self.__connection.ping()  # Ping so that device starts sending to computer's IP
        if ping_response.result != ximu3.RESULT_OK:
            raise Exception(f"Ping failed for {connection_info.to_string()}")

        self.__prefix = f"{ping_response.device_name} {ping_response.serial_number} "
        device_name = ping_response.device_name.strip()
        serial = ping_response.serial_number.strip()

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
        data_str = message.to_string()
        parts = data_str.split()
        if len(parts) < 4:
            print("Unexpected quaternion message format:", data_str)
            return None
        device_name = self.__prefix.split()[0]
        timestamp = parts[0]
        q0, q1, q2, q3 = parts[-4:]
        return [device_name, timestamp, q0, q1, q2, q3]

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
    # 1) Create DataLogger parent directory if not present
    parent_dir = "DataLogger"
    os.makedirs(parent_dir, exist_ok=True)

    # 2) Create a timestamped folder for this ses
    #    Example format: YYYY-MM-DD_HH-MM-SS
    session_dir_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir_path = os.path.join(parent_dir, session_dir_name)
    os.makedirs(session_dir_path, exist_ok=True)

    # Detect available UDP connections
    detected_messages = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
    connections = [Connection(m.to_udp_connection_info(), session_dir_path) for m in detected_messages]

    if not connections:
        raise Exception("No UDP connections available")

    # Example commands to each connection
    for connection in connections:
        connection.send_command("udpDataMessagesEnabled", True)
        connection.send_command("inertialMessageRateDivisor", 8)

    # Allow some time for data to stream
    time.sleep(20)

    # Close each connection properly
    for connection in connections:
        connection.close()

