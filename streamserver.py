import io
import logging
import socketserver
import time
import threading
import os
import subprocess
import sys
from datetime import datetime
from collections import deque
from threading import Condition
from http import server

# Check and install required packages
def check_and_install_packages():
    """Check if OpenCV and NumPy are installed, install if missing"""
    required_packages = {
        'cv2': 'opencv-python',
        'numpy': 'numpy'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
            logging.info(f"✅ {module} is available")
        except ImportError:
            logging.warning(f"❌ {module} not found, will install {package}")
            missing_packages.append(package)
    
    if missing_packages:
        logging.info("Installing missing packages...")
        for package in missing_packages:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                logging.info(f"✅ Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                logging.error(f"❌ Failed to install {package}: {e}")
                sys.exit(1)

# Check dependencies before importing
check_and_install_packages()

# Now import the required packages
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
<title>Motion Detection Stream</title>
</head>
<body>
<h1>🎥 Motion Detection Stream</h1>
<div class="status-bar">
    <div class="status-item">
        <span class="label">Status:</span>
        <span class="status">● ACTIVE</span>
    </div>
    <div class="status-item">
        <span class="label">Motion:</span>
        <span class="motion-status" id="motion-status">Monitoring...</span>
    </div>
    <div class="status-item">
        <span class="label">Recording:</span>
        <span class="recording-status" id="recording-status">Standby</span>
    </div>
</div>
<div class="info-panel">
    <div class="feature">🔍 OpenCV Motion Detection</div>
    <div class="feature">📹 10sec Pre/Post Recording</div>
    <div class="feature">💾 Auto-Save with Timestamp</div>
</div>
<div class="camera">
    <img src="stream.mjpg" width="640" height="480" />
</div>
<div class="footer">
    <p>Recordings saved with format: motion_YYYYMMDD_HHMMSS.mp4</p>
    <p>Pre-buffer: 10 seconds | Post-motion: 10 seconds</p>
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
    .status-bar {
        display: flex;
        justify-content: space-around;
        background: #2a2a2a;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #00ff88;
    }
    .status-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 5px;
    }
    .label {
        font-size: 0.9em;
        color: #ccc;
    }
    .status {
        color: #00ff88;
        font-weight: bold;
        animation: pulse 2s infinite;
    }
    .motion-status {
        color: #ffaa00;
        font-weight: bold;
    }
    .recording-status {
        color: #ff4444;
        font-weight: bold;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.6; }
        100% { opacity: 1; }
    }
    .info-panel {
        display: flex;
        justify-content: space-around;
        margin-bottom: 20px;
    }
    .feature {
        background: #333;
        padding: 8px 12px;
        border-radius: 5px;
        font-size: 0.9em;
        color: #ddd;
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
    .footer {
        text-align: center;
        margin-top: 20px;
        color: #888;
        font-size: 0.9em;
    }
    .footer p {
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
    def __init__(self, threshold=25, min_area=1000, learning_rate=0.001):
        self.threshold = threshold
        self.min_area = min_area
        self.learning_rate = learning_rate
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, 
            varThreshold=50, 
            history=500
        )
        self.motion_detected = False
        self.last_motion_time = 0
        
    def detect_motion(self, frame):
        """Detect motion in the given frame"""
        if frame is None:
            return False
            
        # Apply background subtraction with learning rate
        fg_mask = self.background_subtractor.apply(frame, learningRate=self.learning_rate)
        
        # Remove noise with morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
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
    def __init__(self, max_duration=10, fps=30):
        self.max_frames = int(max_duration * fps)
        self.buffer = deque(maxlen=self.max_frames)
        self.fps = fps
        
    def add_frame(self, frame):
        """Add a frame to the circular buffer"""
        timestamp = time.time()
        self.buffer.append((frame.copy(), timestamp))
        
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
        self.post_motion_frames = 0
        self.post_motion_duration = 10  # seconds
        self.fps = 30
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def start_recording(self, prebuffer_frames, frame_size):
        """Start recording with prebuffer frames"""
        if self.is_recording:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.current_writer = cv2.VideoWriter(
            self.current_filename, fourcc, self.fps, frame_size
        )
        
        if not self.current_writer.isOpened():
            logging.error(f"Failed to open video writer for {self.current_filename}")
            return
            
        # Write prebuffer frames first
        for frame, timestamp in prebuffer_frames:
            if frame is not None:
                self.current_writer.write(frame)
                
        self.is_recording = True
        self.recording_start_time = time.time()
        self.post_motion_frames = 0
        logging.info(f"🔴 Started recording: {self.current_filename}")
        
    def write_frame(self, frame):
        """Write a frame to the current recording"""
        if self.is_recording and self.current_writer:
            self.current_writer.write(frame)
            
    def update_post_motion(self, motion_detected):
        """Update post-motion recording counter"""
        if not self.is_recording:
            return False
            
        if motion_detected:
            self.post_motion_frames = 0  # Reset counter when motion detected
            return True
        else:
            self.post_motion_frames += 1
            max_post_frames = self.post_motion_duration * self.fps
            
            if self.post_motion_frames >= max_post_frames:
                self.stop_recording()
                return False
            return True
            
    def stop_recording(self):
        """Stop the current recording"""
        if not self.is_recording:
            return
            
        if self.current_writer:
            self.current_writer.release()
            self.current_writer = None
            
        duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        logging.info(f"⏹️  Stopped recording: {self.current_filename} (Duration: {duration:.1f}s)")
        
        self.is_recording = False
        self.current_filename = None
        self.recording_start_time = None
        self.post_motion_frames = 0

class MotionStreamingOutput(StreamingOutput):
    def __init__(self, motion_detector, video_recorder, circular_buffer):
        super().__init__()
        self.motion_detector = motion_detector
        self.video_recorder = video_recorder
        self.circular_buffer = circular_buffer
        self.frame_count = 0
        self.motion_status = "No Motion"
        self.motion_processing_active = True
        self.latest_frame_for_processing = None
        
        # Start motion processing thread
        self.motion_thread = threading.Thread(target=self._motion_processing_loop, daemon=True)
        self.motion_thread.start()
        
    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.last_frame_time = time.time()
            
            # Store frame for motion processing without blocking streaming
            self.frame_count += 1
            if self.frame_count % 5 == 0:  # Process every 5th frame (reduced from 3)
                self.latest_frame_for_processing = buf
                
            self.condition.notify_all()
            
    def _motion_processing_loop(self):
        """Separate thread for motion detection processing"""
        while self.motion_processing_active:
            try:
                if self.latest_frame_for_processing is not None:
                    # Process the latest frame
                    frame_buf = self.latest_frame_for_processing
                    self.latest_frame_for_processing = None
                    
                    self._process_frame_for_motion(frame_buf)
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)  # Process at most 10 times per second
                
            except Exception as e:
                logging.error(f"Motion processing error: {e}")
                time.sleep(0.5)  # Longer delay on error
                
    def stop_motion_processing(self):
        """Stop the motion processing thread"""
        self.motion_processing_active = False
            
    def _process_frame_for_motion(self, jpeg_buf):
        """Process JPEG buffer for motion detection and recording (non-blocking)"""
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
            
            if motion_detected:
                self.motion_status = "🔴 MOTION DETECTED"
                
                # Start recording if not already recording
                if not self.video_recorder.is_recording:
                    prebuffer_frames = self.circular_buffer.get_prebuffer_frames()
                    frame_size = (frame.shape[1], frame.shape[0])
                    self.video_recorder.start_recording(prebuffer_frames, frame_size)
                    
            else:
                self.motion_status = "🟢 No Motion"
                
            # Handle recording state
            if self.video_recorder.is_recording:
                self.video_recorder.write_frame(frame)
                
                # Check if we should continue recording
                if not self.video_recorder.update_post_motion(motion_detected):
                    self.motion_status = "🟢 No Motion"
                    
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
        elif self.path == '/favicon.ico':
            # Return empty favicon to prevent 404 errors
            self.send_response(204)  # No Content
            self.end_headers()
        elif self.path.startswith('/apple-touch-icon') or self.path.endswith('.png') or self.path.endswith('.ico'):
            # Handle common mobile/browser icon requests
            self.send_response(204)  # No Content
            self.end_headers()
        else:
            # Log unknown requests for debugging
            logging.debug(f"404 request from {self.client_address}: {self.path}")
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
    """Main server loop with motion detection"""
    restart_count = 0
    
    while True:
        try:
            restart_count += 1
            logging.info(f"🚀 Starting motion detection stream server (attempt #{restart_count})")
            
            # Initialize camera
            picam2 = initialize_camera()
            
            try:
                # Create motion detection components
                motion_detector = MotionDetector(threshold=25, min_area=1000)
                video_recorder = VideoRecorder("recordings")
                circular_buffer = CircularVideoBuffer(max_duration=10, fps=30)
                
                # Create motion-aware output
                global output
                output = MotionStreamingOutput(motion_detector, video_recorder, circular_buffer)
                watchdog = StreamWatchdog()
                
                logging.info("🔍 Motion detection system initialized")
                logging.info("📊 Configuration:")
                logging.info(f"   - Motion threshold: {motion_detector.threshold}")
                logging.info(f"   - Minimum area: {motion_detector.min_area} pixels")
                logging.info(f"   - Pre-record buffer: 10 seconds")
                logging.info(f"   - Post-motion recording: 10 seconds")
                logging.info(f"   - Recording directory: {video_recorder.output_dir}")
                logging.info(f"   - Video format: motion_YYYYMMDD_HHMMSS.mp4")
                
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
                logging.info(f"🌐 Server started on http://localhost:8000")
                logging.info("🎥 Motion detection is ACTIVE - recordings will be saved automatically")
                
                try:
                    server.serve_forever()
                finally:
                    watchdog.stop()
                    # Stop motion processing thread
                    output.stop_motion_processing()
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
