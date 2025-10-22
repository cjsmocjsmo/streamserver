import io
import logging
import socketserver
import time
import threading
import os
from datetime import datetime
from collections import deque
from threading import Condition
from http import server

import cv2
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder, H264Encoder
from picamera2.outputs import FileOutput

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PAGE = """\
<html>
<head>
<title>Raspberry Pi Motion Detection Stream</title>
<meta http-equiv="refresh" content="30">
</head>
<body>
<h1>🎥 Motion Detection Stream</h1>
<div class="info">
    <div class="status">
        <span class="status-label">Status:</span>
        <span class="status-active">● ACTIVE</span>
    </div>
    <div class="features">
        <div class="feature">🔍 Motion Detection Enabled</div>
        <div class="feature">📹 Auto Recording on Motion</div>
        <div class="feature">⏱️ 5sec Pre-buffer</div>
    </div>
</div>
<div class="camera">
    <img src="stream.mjpg" width="640" height="480" />
</div>
<div class="controls">
    <p>Recordings are automatically saved when motion is detected</p>
    <p>Check the 'recordings' directory for saved videos</p>
</div>
</body>
<style>
    body {
        background: #1a1a1a;
        color: #ffffff;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        margin: 0;
        padding: 20px;
    }
    h1 {
        text-align: center;
        color: #00ff88;
        margin-bottom: 20px;
        text-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
    }
    .info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #2a2a2a;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #00ff88;
    }
    .status {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .status-label {
        font-weight: bold;
    }
    .status-active {
        color: #00ff88;
        font-weight: bold;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .features {
        display: flex;
        gap: 15px;
    }
    .feature {
        background: #333;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.9em;
    }
    .camera {
        display: flex;
        justify-content: center;
        align-items: center;
        background: #000;
        padding: 10px;
        border-radius: 10px;
        border: 2px solid #00ff88;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.2);
    }
    .camera img {
        border-radius: 5px;
    }
    .controls {
        text-align: center;
        margin-top: 20px;
        color: #ccc;
    }
    .controls p {
        margin: 5px 0;
    }
</style>
</html>"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()
        self.last_frame_time = time.time()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.last_frame_time = time.time()
            self.condition.notify_all()

class MotionDetector:
    def __init__(self, threshold=25, min_area=500, blur_size=21):
        self.threshold = threshold
        self.min_area = min_area
        self.blur_size = blur_size
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50, history=500
        )
        self.motion_detected = False
        self.last_motion_time = 0
        
    def detect_motion(self, frame):
        """Detect motion in the given frame"""
        if frame is None:
            return False
            
        # Apply background subtraction
        fg_mask = self.background_subtractor.apply(frame)
        
        # Remove noise with morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check if any contour is large enough to be considered motion
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                motion_detected = True
                break
                
        if motion_detected:
            self.last_motion_time = time.time()
            
        self.motion_detected = motion_detected
        return motion_detected

class CircularVideoBuffer:
    def __init__(self, max_duration=5, fps=30):
        self.max_frames = int(max_duration * fps)
        self.buffer = deque(maxlen=self.max_frames)
        self.fps = fps
        
    def add_frame(self, frame):
        """Add a frame to the circular buffer"""
        self.buffer.append((frame.copy(), time.time()))
        
    def get_prebuffer_frames(self):
        """Get all frames currently in the buffer"""
        return list(self.buffer)
        
    def clear(self):
        """Clear the buffer"""
        self.buffer.clear()

class VideoRecorder:
    def __init__(self, output_dir="recordings"):
        self.output_dir = output_dir
        self.is_recording = False
        self.current_writer = None
        self.current_filename = None
        self.recording_start_time = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def start_recording(self, prebuffer_frames, frame_size, fps=30):
        """Start recording with prebuffer frames"""
        if self.is_recording:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.current_writer = cv2.VideoWriter(
            self.current_filename, fourcc, fps, frame_size
        )
        
        if not self.current_writer.isOpened():
            logging.error(f"Failed to open video writer for {self.current_filename}")
            return
            
        # Write prebuffer frames first
        for frame, _ in prebuffer_frames:
            if frame is not None:
                self.current_writer.write(frame)
                
        self.is_recording = True
        self.recording_start_time = time.time()
        logging.info(f"Started recording: {self.current_filename}")
        
    def write_frame(self, frame):
        """Write a frame to the current recording"""
        if self.is_recording and self.current_writer:
            self.current_writer.write(frame)
            
    def stop_recording(self):
        """Stop the current recording"""
        if not self.is_recording:
            return
            
        if self.current_writer:
            self.current_writer.release()
            self.current_writer = None
            
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        logging.info(f"Stopped recording: {self.current_filename} (Duration: {duration:.1f}s)")
        
        self.is_recording = False
        self.current_filename = None
        self.recording_start_time = None

class MotionStreamingOutput(StreamingOutput):
    def __init__(self, motion_detector, video_recorder, circular_buffer):
        super().__init__()
        self.motion_detector = motion_detector
        self.video_recorder = video_recorder
        self.circular_buffer = circular_buffer
        self.motion_timeout = 5.0  # Stop recording after 5 seconds of no motion
        self.frame_count = 0
        
    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.last_frame_time = time.time()
            
            # Process frame for motion detection every few frames to save CPU
            self.frame_count += 1
            if self.frame_count % 3 == 0:  # Process every 3rd frame
                self._process_frame_for_motion(buf)
                
            self.condition.notify_all()
            
    def _process_frame_for_motion(self, jpeg_buf):
        """Process JPEG buffer for motion detection and recording"""
        try:
            # Convert JPEG buffer to OpenCV frame
            nparr = np.frombuffer(jpeg_buf, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
                
            # Add frame to circular buffer
            self.circular_buffer.add_frame(frame)
            
            # Detect motion
            motion_detected = self.motion_detector.detect_motion(frame)
            
            current_time = time.time()
            
            if motion_detected:
                # Start recording if not already recording
                if not self.video_recorder.is_recording:
                    prebuffer_frames = self.circular_buffer.get_prebuffer_frames()
                    frame_size = (frame.shape[1], frame.shape[0])
                    self.video_recorder.start_recording(prebuffer_frames, frame_size)
                    
                # Write current frame to recording
                if self.video_recorder.is_recording:
                    self.video_recorder.write_frame(frame)
                    
            else:
                # Check if we should stop recording (no motion for timeout period)
                if (self.video_recorder.is_recording and 
                    current_time - self.motion_detector.last_motion_time > self.motion_timeout):
                    self.video_recorder.stop_recording()
                    
                # Continue writing frames for a bit after motion stops
                elif self.video_recorder.is_recording:
                    self.video_recorder.write_frame(frame)
                    
        except Exception as e:
            logging.error(f"Error processing frame for motion detection: {e}")

class StreamWatchdog:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.is_monitoring = True
    
    def check_health(self, output):
        return (time.time() - output.last_frame_time) < self.timeout
    
    def stop(self):
        self.is_monitoring = False

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            self.handle_streaming_client()
        else:
            self.send_error(404)
            self.end_headers()

    def handle_streaming_client(self):
        frame_count = 0
        try:
            while True:
                with output.condition:
                    # Add timeout to prevent indefinite waiting
                    if not output.condition.wait(timeout=30):
                        logging.warning(f"Frame timeout for client {self.client_address} - stream may be dead")
                        break
                    frame = output.frame
                
                if frame is None:
                    continue
                    
                # Send frame with error checking
                try:
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    frame_count += 1
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    logging.info(f"Client {self.client_address} disconnected after {frame_count} frames")
                    break
                    
        except Exception as e:
            logging.warning(f"Streaming error for client {self.client_address}: {e}")

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def initialize_camera(max_retries=3, retry_delay=2):
    """Initialize camera with retry logic"""
    for attempt in range(max_retries):
        try:
            picam2 = Picamera2()
            picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
            logging.info(f"Camera initialized successfully on attempt {attempt + 1}")
            return picam2
        except Exception as e:
            logging.error(f"Camera initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

def start_recording_with_recovery(picam2, output, max_retries=3):
    """Start recording with retry logic"""
    for attempt in range(max_retries):
        try:
            picam2.start_recording(JpegEncoder(), FileOutput(output))
            logging.info("Recording started successfully")
            return True
        except Exception as e:
            logging.error(f"Recording start attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                try:
                    picam2.stop_recording()  # Ensure clean state
                except:
                    pass
            else:
                logging.error("Failed to start recording after all retries")
                return False
    return False

def monitor_stream_health(watchdog, picam2, output):
    """Monitor stream health and attempt recovery if needed"""
    consecutive_failures = 0
    while watchdog.is_monitoring:
        time.sleep(10)  # Check every 10 seconds
        
        if not watchdog.check_health(output):
            consecutive_failures += 1
            logging.warning(f"Stream appears dead (failure #{consecutive_failures}) - attempting recovery")
            
            try:
                # Stop current recording
                picam2.stop_recording()
                time.sleep(2)
                
                # Restart recording
                if start_recording_with_recovery(picam2, output):
                    logging.info("Stream recovery successful")
                    consecutive_failures = 0
                else:
                    logging.error("Stream recovery failed")
                    
            except Exception as e:
                logging.error(f"Recovery attempt failed: {e}")
                
            # If too many consecutive failures, log critical error
            if consecutive_failures >= 3:
                logging.critical("Multiple stream recovery failures - manual intervention may be required")
                
        else:
            if consecutive_failures > 0:
                logging.info("Stream health restored")
                consecutive_failures = 0

def run_stream_server():
    """Main server loop with recovery and motion detection"""
    restart_count = 0
    
    while True:
        try:
            restart_count += 1
            logging.info(f"Starting stream server with motion detection (attempt #{restart_count})")
            
            # Initialize camera
            picam2 = initialize_camera()
            
            try:
                # Create motion detection components
                motion_detector = MotionDetector(threshold=25, min_area=500)
                video_recorder = VideoRecorder("recordings")
                circular_buffer = CircularVideoBuffer(max_duration=5, fps=30)
                
                # Create motion-aware output
                global output
                output = MotionStreamingOutput(motion_detector, video_recorder, circular_buffer)
                watchdog = StreamWatchdog()
                
                logging.info("Motion detection system initialized")
                logging.info("- Motion threshold: 25")
                logging.info("- Minimum area: 500 pixels")
                logging.info("- Pre-record buffer: 5 seconds")
                logging.info("- Post-motion timeout: 5 seconds")
                logging.info(f"- Recording directory: {video_recorder.output_dir}")
                
                # Start recording
                if not start_recording_with_recovery(picam2, output):
                    raise Exception("Failed to start recording")
                
                # Start health monitoring in separate thread
                watchdog_thread = threading.Thread(
                    target=monitor_stream_health, 
                    args=(watchdog, picam2, output),
                    daemon=True
                )
                watchdog_thread.start()
                
                # Start HTTP server
                address = ('', 8000)
                server = StreamingServer(address, StreamingHandler)
                logging.info(f"Server started on http://localhost:8000")
                logging.info("Motion detection is active - recordings will be saved when motion is detected")
                
                try:
                    server.serve_forever()
                finally:
                    watchdog.stop()
                    # Stop any ongoing recording
                    if video_recorder.is_recording:
                        video_recorder.stop_recording()
                    server.shutdown()
                    
            finally:
                try:
                    picam2.stop_recording()
                    picam2.close()
                except:
                    pass
                    
        except KeyboardInterrupt:
            logging.info("Server shutdown requested by user")
            break
        except Exception as e:
            logging.error(f"Server crashed: {e}")
            if restart_count < 5:
                logging.info(f"Restarting server in 5 seconds... (attempt {restart_count + 1}/5)")
                time.sleep(5)
            else:
                logging.critical("Too many restart attempts - giving up")
                break

if __name__ == "__main__":
    run_stream_server()
