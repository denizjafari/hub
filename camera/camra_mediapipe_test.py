#!/usr/bin/env python3
"""
Pi Camera + MediaPipe with real-time-correct recording.

- If ffmpeg is available: pipe frames to ffmpeg with wall-clock timestamps (VFR)
  so the MP4 duration matches real recording time even if FPS varies.
- Else: warm up to estimate actual FPS and open OpenCV VideoWriter with that FPS
  (closer to real-time than a hard-coded 30 fps).

Also includes resilient preview:
  * Tries Picamera2 Qt preview + overlay (best), else falls back to OpenCV window.

Stop keys:
  - Qt overlay path: Ctrl+C in terminal
  - OpenCV window path: press 'q'
"""

from pathlib import Path
from datetime import datetime
import os, time, cv2, numpy as np, shutil, subprocess, sys

# ---------- USER SETTINGS ----------
video_name       = "demo_session"     # folder to store recordings
resolution       = (1280, 720)        # (width, height)
camera_fps_req   = 30                 # requested sensor/output fps
flip_horizontal  = True
mediapipe_mode   = "pose"         # "holistic" | "pose" | "hands" | "face"
show_preview     = True               # live preview on screen
warmup_seconds   = 2.0                # only used if ffmpeg is NOT available
ffmpeg_crf       = 23                 # lower = better quality, bigger file
ffmpeg_preset    = "veryfast"         # ultrafast | superfast | veryfast | faster | fast | medium | ...
# -----------------------------------

# Make Qt happy on Wayland/Bookworm if present (harmless otherwise)
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
if "XDG_RUNTIME_DIR" not in os.environ:
    rd = f"/tmp/{os.getuid()}-runtime"
    os.makedirs(rd, exist_ok=True)
    os.chmod(rd, 0o700)
    os.environ["XDG_RUNTIME_DIR"] = rd

from picamera2 import Picamera2
# Choose best Picamera2 preview class present
try:
    from picamera2.previews import QtGlPreview as PiPreview
    _preview_kind = "qtgl"
except Exception:
    try:
        from picamera2.previews import QtPreview as PiPreview
        _preview_kind = "qt"
    except Exception:
        from picamera2.previews import NullPreview as PiPreview
        _preview_kind = "null"

import mediapipe as mp
mp_draw   = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


def open_mediapipe(mode: str):
    mode = (mode or "holistic").lower()
    if mode == "pose":
        mp_pose = mp.solutions.pose
        sol = mp_pose.Pose(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        def draw(img, r):
            if r.pose_landmarks:
                mp_draw.draw_landmarks(img, r.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                       landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style())
        return sol, draw
    if mode == "hands":
        mp_hands = mp.solutions.hands
        sol = mp_hands.Hands(model_complexity=0, max_num_hands=2,
                             min_detection_confidence=0.5, min_tracking_confidence=0.5)
        def draw(img, r):
            if r.multi_hand_landmarks:
                for h in r.multi_hand_landmarks:
                    mp_draw.draw_landmarks(img, h, mp_hands.HAND_CONNECTIONS)
        return sol, draw
    if mode == "face":
        mp_face = mp.solutions.face_mesh
        sol = mp_face.FaceMesh(static_image_mode=False, refine_landmarks=False, max_num_faces=1,
                               min_detection_confidence=0.5, min_tracking_confidence=0.5)
        def draw(img, r):
            if r.multi_face_landmarks:
                for f in r.multi_face_landmarks:
                    mp_draw.draw_landmarks(img, f, mp_face.FACEMESH_TESSELATION, None,
                                           mp_styles.get_default_face_mesh_tesselation_style())
                    mp_draw.draw_landmarks(img, f, mp_face.FACEMESH_CONTOURS, None,
                                           mp_styles.get_default_face_mesh_contours_style())
        return sol, draw

    # default: holistic
    mp_hol = mp.solutions.holistic
    sol = mp_hol.Holistic(model_complexity=0, refine_face_landmarks=False,
                          min_detection_confidence=0.5, min_tracking_confidence=0.5)
    def draw(img, r):
        if r.face_landmarks:
            mp_draw.draw_landmarks(img, r.face_landmarks, mp_hol.FACEMESH_TESSELATION, None,
                                   mp_styles.get_default_face_mesh_tesselation_style())
            mp_draw.draw_landmarks(img, r.face_landmarks, mp_hol.FACEMESH_CONTOURS, None,
                                   mp_styles.get_default_face_mesh_contours_style())
        if r.pose_landmarks:
            mp_draw.draw_landmarks(img, r.pose_landmarks, mp_hol.POSE_CONNECTIONS,
                                   landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style())
        if r.left_hand_landmarks:
            mp_draw.draw_landmarks(img, r.left_hand_landmarks, mp_hol.HAND_CONNECTIONS)
        if r.right_hand_landmarks:
            mp_draw.draw_landmarks(img, r.right_hand_landmarks, mp_hol.HAND_CONNECTIONS)
    return sol, draw


def start_ffmpeg_writer(path: Path, size, crf=23, preset="veryfast"):
    """
    Start an ffmpeg process that accepts raw BGR frames on stdin and writes MP4 with wall-clock timestamps.
    Requires: sudo apt install -y ffmpeg
    """
    w, h = size
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-video_size", f"{w}x{h}",
        "-use_wallclock_as_timestamps", "1",  # derive PTS from wall clock (VFR)
        "-i", "-",                            # read raw frames from stdin
        "-an",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-vf", "format=yuv420p",              # playback compatibility
        "-movflags", "+faststart",
        str(path)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    return proc


def make_cv_writer(path_stub: Path, size, fps):
    """Open a cv2.VideoWriter with mp4v; fall back to MJPG/AVI if needed."""
    out_mp4 = path_stub.with_suffix(".mp4")
    w = cv2.VideoWriter(str(out_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if w.isOpened():
        return w, out_mp4
    out_avi = path_stub.with_suffix(".avi")
    w = cv2.VideoWriter(str(out_avi), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    if not w.isOpened():
        raise RuntimeError("Failed to open a VideoWriter for output.")
    return w, out_avi


def main():
    # --- output path ---
    out_dir = Path.cwd() / video_name
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_stub = out_dir / f"{stamp}_annotated"  # we’ll add suffix below

    # --- camera ---
    picam2 = Picamera2()
    cfg = picam2.create_video_configuration(
        main={"size": resolution, "format": "RGB888"},
        controls={"FrameRate": camera_fps_req}
    )
    picam2.configure(cfg)
    picam2.start()

    # --- preview: Qt overlay -> OpenCV fallback ---
    started_qt_preview = False
    use_overlay = False
    if show_preview:
        if _preview_kind != "null":
            try:
                picam2.start_preview(PiPreview())  # may raise RuntimeError
                started_qt_preview = True
                use_overlay = True
            except RuntimeError as e:
                print("[WARN] Qt preview not usable:", e)
                print("[INFO] Falling back to OpenCV window (press 'q' to quit).")
                cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)
        else:
            print("[INFO] Qt preview not available; using OpenCV window.")
            cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

    # --- mediapipe ---
    solution, draw = open_mediapipe(mediapipe_mode)

    # --- choose writer: ffmpeg (VFR) if available, else OpenCV with warm-up FPS ---
    have_ffmpeg = shutil.which("ffmpeg") is not None
    ffmpeg_proc = None
    writer = None
    out_path = None

    if have_ffmpeg:
        out_path = out_stub.with_suffix(".mp4")
        print(f"[INFO] Recording (ffmpeg VFR) to: {out_path}")
        ffmpeg_proc = start_ffmpeg_writer(out_path, resolution, crf=ffmpeg_crf, preset=ffmpeg_preset)
    else:
        print("[INFO] ffmpeg not found — will estimate FPS and use OpenCV writer.")
        # Warmup to estimate actual FPS
        warm_frames = 0
        t0 = time.time()
        while time.time() - t0 < warmup_seconds:
            rgb = picam2.capture_array()
            if flip_horizontal:
                rgb = cv2.flip(rgb, 1)
            res = solution.process(rgb)
            annotated = rgb.copy()
            draw(annotated, res)

            bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
            warm_frames += 1

            if use_overlay:
                bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA); bgra[..., 3] = 230
                picam2.set_overlay(bgra)
            elif show_preview:
                cv2.imshow("Preview", bgr)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        est_fps = max(5.0, min(30.0, warm_frames / max(1e-6, (time.time() - t0))))
        writer, out_path = make_cv_writer(out_stub, resolution, est_fps)
        print(f"[INFO] Recording (OpenCV @ ~{est_fps:.1f} fps) to: {out_path}")

    # --- main loop ---
    frames, t_start = 0, time.time()
    try:
        while True:
            rgb = picam2.capture_array()
            if flip_horizontal:
                rgb = cv2.flip(rgb, 1)

            result = solution.process(rgb)
            annotated = rgb.copy()
            draw(annotated, result)

            bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

            # Write frame
            if ffmpeg_proc is not None:
                try:
                    ffmpeg_proc.stdin.write(bgr.tobytes())
                except (BrokenPipeError, AttributeError):
                    print("\n[ERROR] ffmpeg pipe closed unexpectedly.")
                    break
            else:
                writer.write(bgr)

            # Preview
            if use_overlay:
                bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA); bgra[..., 3] = 230
                picam2.set_overlay(bgra)
            elif show_preview:
                cv2.imshow("Preview", bgr)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            frames += 1
            if frames % 30 == 0:
                dt = max(1e-6, time.time() - t_start)
                print(f"[INFO] ~{frames/dt:.1f} FPS, {frames} frames", end="\r")

    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup writers
        if ffmpeg_proc is not None:
            try:
                ffmpeg_proc.stdin.close()
            except Exception:
                pass
            ffmpeg_proc.wait()
        if writer is not None:
            writer.release()

        # Cleanup preview / camera
        solution.close()
        if started_qt_preview:
            try:
                picam2.stop_preview()
            except Exception:
                pass
        elif show_preview:
            cv2.destroyAllWindows()
        picam2.stop()

        if out_path:
            print(f"\n[INFO] Saved: {out_path}")
        else:
            print("\n[INFO] Stopped without output file.")
        # Tiny summary
        if frames:
            real_dt = max(1e-6, time.time() - t_start)
            print(f"[INFO] Captured {frames} frames over {real_dt:.1f}s (~{frames/real_dt:.1f} fps)")

if __name__ == "__main__":
    main()
