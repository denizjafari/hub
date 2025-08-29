import os
# Disable MediaPipe GPU usage and force software rendering
os.environ['MEDIAPIPE_DISABLE_GPU'] = '1'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'

import sys
import time
import csv
import cv2
# Disable OpenCL in OpenCV to avoid hardware acceleration
cv2.ocl.setUseOpenCL(False)

from datetime import datetime
import ximu3
import mediapipe as mp


class IMUConnection:
    def __init__(self, connection_info, session_dir):
        self._conn = ximu3.Connection(connection_info)
        if self._conn.open() != ximu3.RESULT_OK:
            raise Exception(f"Unable to open {connection_info.to_string()}")
        ping = self._conn.ping()
        if ping.result != ximu3.RESULT_OK:
            raise Exception(f"Ping failed for {connection_info.to_string()}")

        self._prefix = f"{ping.device_name.strip()}_{ping.serial_number.strip()}"
        self.csv_files = {}
        self.csv_writers = {}
        self.callback_configs = {
            "inertial": {
                "header": ["device","timestamp","gyro_x [deg/s]","gyro_y [deg/s]","gyro_z [deg/s]","acc_x [g]","acc_y [g]","acc_z [g]"],
                "parser": self._parse_inertial,
                "register_method": "add_inertial_callback"
            },
            "magnetometer": {
                "header": ["device","timestamp","mag_x [a.u.]","mag_y [a.u.]","mag_z [a.u.]"],
                "parser": self._parse_magnetometer,
                "register_method": "add_magnetometer_callback"
            },
            "quaternion": {
                "header": ["device","timestamp","q0","q1","q2","q3"],
                "parser": self._parse_quaternion,
                "register_method": "add_quaternion_callback"
            },
            "euler_angles": {
                "header": ["device","timestamp","roll [deg]","pitch [deg]","yaw [deg]"],
                "parser": self._parse_euler,
                "register_method": "add_euler_angles_callback"
            }
        }
        for name, cfg in self.callback_configs.items():
            fname = f"{self._prefix}_{name}.csv"
            path = os.path.join(session_dir, fname)
            f = open(path, 'w', newline='')
            writer = csv.writer(f)
            writer.writerow(cfg['header'])
            self.csv_files[name] = f
            self.csv_writers[name] = writer
            register = getattr(self._conn, cfg['register_method'])
            register(lambda msg, n=name: self._handle(n, msg))

    def _handle(self, name, msg):
        row = self.callback_configs[name]['parser'](msg)
        if row:
            self.csv_writers[name].writerow(row)
            self.csv_files[name].flush()

    def _parse_inertial(self, msg):
        parts = msg.to_string().split()
        if len(parts) < 8:
            return None
        ts = parts[0]
        gx, gy, gz = parts[2:5]
        ax, ay, az = parts[5:8]
        return [self._prefix, ts, gx, gy, gz, ax, ay, az]

    def _parse_magnetometer(self, msg):
        parts = msg.to_string().split()
        if len(parts) < 6:
            return None
        ts = parts[0]
        mx, my, mz = parts[2:5]
        return [self._prefix, ts, mx, my, mz]

    def _parse_quaternion(self, msg):
        parts = msg.to_string().split()
        if len(parts) < 5:
            return None
        ts = parts[0]
        q0, q1, q2, q3 = parts[-4:]
        return [self._prefix, ts, q0, q1, q2, q3]

    def _parse_euler(self, msg):
        parts = msg.to_string().split()
        if len(parts) < 4:
            return None
        ts = parts[0]
        r, p, y = parts[1:4]
        return [self._prefix, ts, r, p, y]

    def send_command(self, key, value=None):
        if value is None:
            val = 'null'
        elif isinstance(value, bool):
            val = str(value).lower()
        elif isinstance(value, str):
            val = f'"{value}"'
        else:
            val = str(value)
        cmd = f'{{"{key}":{val}}}'
        resp = self._conn.send_commands([cmd], 2, 500)
        if not resp:
            raise Exception(f"No response to {cmd}")

    def close(self):
        self._conn.close()
        for f in self.csv_files.values():
            f.close()


class VisionRecorder:
    def __init__(self, session_dir, duration):
        self.session_dir = session_dir
        self.duration = duration
        self.camera = cv2.VideoCapture(0)
        w = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.camera.get(cv2.CAP_PROP_FPS) or 30.0
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.raw_writer = cv2.VideoWriter(
            os.path.join(session_dir, 'raw_video.avi'), fourcc, fps, (w, h)
        )
        self.ann_writer = cv2.VideoWriter(
            os.path.join(session_dir, 'annotated_video.avi'), fourcc, fps, (w, h)
        )
        csv_path = os.path.join(session_dir, 'pose_landmarks.csv')
        self.pose_file = open(csv_path, 'w', newline='')
        self.pose_writer = csv.writer(self.pose_file)
        # Create a wide header for all Pose landmarks
        num_landmarks = len(mp.solutions.pose.PoseLandmark)
        headers = ['frame', 'timestamp']
        for i in range(num_landmarks):
            headers += [
                f'landmark{i}_x',
                f'landmark{i}_y',
                f'landmark{i}_z',
                f'landmark{i}_visibility'
            ]
        self.pose_writer.writerow(headers)

        self.pose = mp.solutions.pose.Pose(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.drawer = mp.solutions.drawing_utils

    def record(self):
        start = time.time()
        frame_idx = 0
        num_landmarks = len(mp.solutions.pose.PoseLandmark)
        cv2.namedWindow('Pose', cv2.WINDOW_NORMAL)
        try:
            while True:
                now = time.time()
                if now - start >= self.duration:
                    break
                ret, frame = self.camera.read()
                if not ret:
                    break
                ts = now
                self.raw_writer.write(frame)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = self.pose.process(rgb)
                ann = frame.copy()
                if res.pose_landmarks:
                    self.drawer.draw_landmarks(
                        ann,
                        res.pose_landmarks,
                        mp.solutions.pose.POSE_CONNECTIONS
                    )
                    landmarks = res.pose_landmarks.landmark
                else:
                    landmarks = None

                # Build one row per frame with all landmark columns
                row = [frame_idx, ts]
                if landmarks:
                    for lm in landmarks:
                        row += [lm.x, lm.y, lm.z, lm.visibility]
                else:
                    row += [None] * (4 * num_landmarks)
                self.pose_writer.writerow(row)

                self.ann_writer.write(ann)
                cv2.imshow('Pose', ann)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                frame_idx += 1
        finally:
            self.camera.release()
            self.raw_writer.release()
            self.ann_writer.release()
            self.pose_file.close()
            cv2.destroyAllWindows()
            self.pose.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python imu_camera_recorder.py <duration_seconds>")
        sys.exit(1)
    try:
        duration_sec = float(sys.argv[1])
    except ValueError:
        print("Error: duration must be a number.")
        sys.exit(1)

    # Prepare session directory
    base = 'DataLogger'
    os.makedirs(base, exist_ok=True)
    sess = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = os.path.join(base, sess)
    os.makedirs(session_dir, exist_ok=True)

    # Initialize IMUs
    msgs = ximu3.NetworkAnnouncement().get_messages_after_short_delay()
    imu_conns = [IMUConnection(m.to_udp_connection_info(), session_dir) for m in msgs]
    for imu in imu_conns:
        imu.send_command('udpDataMessagesEnabled', True)
        imu.send_command('inertialMessageRateDivisor', 8)

    # Record camera + pose for fixed duration
    recorder = VisionRecorder(session_dir, duration_sec)
    try:
        recorder.record()
    finally:
        for imu in imu_conns:
            imu.close()
        print("Recording completed.")