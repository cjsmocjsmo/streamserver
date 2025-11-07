#!/usr/bin/env python3
"""
RTSP Stream Server (Reconstructed)
A hardware-accelerated RTSP streaming server for Raspberry Pi camera.
Includes OpenCV-based motion detection, region exclusion, event video saving, MQTT notification, and SCP upload.
"""

import io
import os
import cv2
import numpy as np
import socket
import struct
import threading
import time
import random
import collections
from datetime import datetime
import glob
import subprocess
try:
    import paho.mqtt.publish as publish
except ImportError:
    publish = None
try:
    import psutil
except ImportError:
    psutil = None

from config import AppConfig
from dependencies import verify_picamera2
from exceptions import CameraError
from logger import setup_logging, get_logger
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

setup_logging()
logger = get_logger(__name__)

if not verify_picamera2():
    raise ImportError("Picamera2 is required but not available")

# --- Motion Detection ---
class MotionDetector:
    def __init__(self, exclude_regions=None, min_area=5000):
        self.prev_gray = None
        self.exclude_regions = exclude_regions or []
        self.min_area = min_area

    def set_exclude_regions(self, regions):
        self.exclude_regions = regions

    def apply_exclusion_mask(self, frame):
        mask = np.ones(frame.shape[:2], dtype="uint8") * 255
        for (x, y, w, h) in self.exclude_regions:
            mask[y:y+h, x:x+w] = 0
        return mask

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        mask = self.apply_exclusion_mask(gray)
        masked_gray = cv2.bitwise_and(gray, gray, mask=mask)
        motion_found = False
        motion_boxes = []
        if self.prev_gray is not None:
            frame_delta = cv2.absdiff(self.prev_gray, masked_gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                if cv2.contourArea(c) < self.min_area:
                    continue
                (x, y, w, h) = cv2.boundingRect(c)
                motion_boxes.append((x, y, w, h))
                motion_found = True
        self.prev_gray = masked_gray.copy()
        return motion_found, motion_boxes

    def draw_exclusion_boxes(self, frame):
        for (x, y, w, h) in self.exclude_regions:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        return frame

# --- Camera Initialization ---
def initialize_camera(config):
    try:
        logger.info("📷 Initializing Picamera2 with H.264 hardware encoding...")
        picam2 = Picamera2()
        video_config = picam2.create_video_configuration(
            main={"size": config.camera.resolution, "format": "YUV420"}
        )
        picam2.configure(video_config)
        encoder = H264Encoder(
            bitrate=1000000,
            repeat=True,
            iperiod=30
        )
        logger.info(f"✅ Camera initialized: {config.camera.resolution} with H.264 hardware encoding")
        return picam2, encoder
    except Exception as e:
        logger.error(f"❌ Camera initialization failed: {e}", exc_info=True)
        raise CameraError(f"Failed to initialize camera: {e}")

# --- Main Streaming Logic ---
def start_camera_streaming(picam2, encoder, output):
    CAMERA_NAME = "pi_cam1"
    VIDEO_DIR = "./events"
    os.makedirs(VIDEO_DIR, exist_ok=True)
    FPS = 10
    PRE_EVENT_SEC = 5
    POST_EVENT_SEC = 5
    buffer_len = FPS * PRE_EVENT_SEC
    frame_buffer = collections.deque(maxlen=buffer_len)
    recording_event = {'active': False}
    post_event_frames = {'count': 0}
    exclude_regions = [(0, 0, 200, 200)]
    motion_detector = MotionDetector(exclude_regions=exclude_regions, min_area=8000)

    def get_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    def send_mqtt_event(camera_name, ts, filepath):
        if publish is None:
            logger.warning("paho-mqtt not installed, cannot send MQTT event")
            return
        ip = get_ip()
        topic = f"cameras/{camera_name}/events"
        payload = {
            "camera": camera_name,
            "timestamp": ts,
            "file": filepath,
            "ip": ip
        }
        try:
            publish.single(topic, str(payload), hostname="10.0.4.40", port=1883)
            logger.info(f"📡 MQTT event sent: {payload}")
        except Exception as e:
            logger.error(f"MQTT publish failed: {e}")

    def save_event_video(frames, event_time):
        ts = event_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{CAMERA_NAME}_{ts}.mp4"
        filepath = os.path.join(VIDEO_DIR, filename)
        height, width, _ = frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filepath, fourcc, FPS, (width, height))
        for f in frames:
            out.write(f)
        out.release()
        logger.info(f"💾 Saved event video: {filepath}")
        send_mqtt_event(CAMERA_NAME, ts, filepath)
        return filepath

    def opencv_motion_loop():
        logger.info("🔍 OpenCV motion detection thread started")
        event_frames = []
        last_event_time = None
        while True:
            try:
                frame = picam2.capture_array("main")
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                motion_found, motion_boxes = motion_detector.detect(frame_bgr)
                annotated = motion_detector.draw_exclusion_boxes(frame_bgr.copy())
                for (x, y, w, h) in motion_boxes:
                    cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 255, 0), 2)
                frame_buffer.append(annotated.copy())
                if motion_found and not recording_event['active']:
                    logger.info(f"🚨 Motion detected! Boxes: {motion_boxes}")
                    recording_event['active'] = True
                    post_event_frames['count'] = FPS * POST_EVENT_SEC
                    event_frames = list(frame_buffer)
                    last_event_time = datetime.now()
                if recording_event['active']:
                    event_frames.append(annotated.copy())
                    if not motion_found:
                        post_event_frames['count'] -= 1
                    else:
                        post_event_frames['count'] = FPS * POST_EVENT_SEC
                    if post_event_frames['count'] <= 0:
                        save_event_video(event_frames, last_event_time)
                        recording_event['active'] = False
                        event_frames = []
                        post_event_frames['count'] = 0
                time.sleep(1.0 / FPS)
            except Exception as e:
                logger.error(f"OpenCV motion detection error: {e}")
                time.sleep(1)

    def scp_videos_when_idle():
        if psutil is None:
            logger.warning("psutil not installed, cannot monitor CPU usage for SCP uploads")
            return
        logger.info("🕒 SCP monitor thread started")
        IDLE_CPU_THRESHOLD = 20.0
        IDLE_PERIOD = 15 * 60
        REMOTE = "teresa@10.0.4.40:/home/teresa/Videos"
        checked_files = set()
        idle_start = None
        while True:
            try:
                cpu = psutil.cpu_percent(interval=10)
                if cpu < IDLE_CPU_THRESHOLD:
                    if idle_start is None:
                        idle_start = time.time()
                    elif time.time() - idle_start >= IDLE_PERIOD:
                        files = sorted(glob.glob(os.path.join(VIDEO_DIR, f"{CAMERA_NAME}_*.mp4")))
                        for f in files:
                            if f in checked_files:
                                continue
                            logger.info(f"⬆️ SCP uploading {f} to {REMOTE}")
                            try:
                                result = subprocess.run(["scp", f, REMOTE], capture_output=True, timeout=120)
                                if result.returncode == 0:
                                    logger.info(f"✅ SCP upload succeeded: {f}")
                                    checked_files.add(f)
                                else:
                                    logger.error(f"❌ SCP upload failed: {f}, {result.stderr.decode()}")
                            except Exception as e:
                                logger.error(f"SCP error: {e}")
                        idle_start = None
                else:
                    idle_start = None
            except Exception as e:
                logger.error(f"SCP monitor error: {e}")
            time.sleep(60)

    try:
        file_output = FileOutput(output)
        picam2.start_recording(encoder, file_output)
        t = threading.Thread(target=opencv_motion_loop, daemon=True)
        t.start()
        scp_thread = threading.Thread(target=scp_videos_when_idle, daemon=True)
        scp_thread.start()
        logger.info("✅ Camera streaming started with motion detection and event handling")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start camera streaming: {e}", exc_info=True)
        return False

# --- Main Entry Point ---
def main():
    config = AppConfig()
    picam2, encoder = initialize_camera(config)
    output = None  # Replace with actual H264StreamOutput instance if needed
    start_camera_streaming(picam2, encoder, output)

if __name__ == "__main__":
    main()