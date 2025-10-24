#!/usr/bin/env python3
"""
Motion Detection Stream Server - Main Application

A professional-grade video streaming server with motion detection capabilities.
"""

import io
import socketserver
import threading
import time
from http import server
from threading import Condition

# Local imports
from config import AppConfig
from database import EventDatabase
from dependencies import check_and_install_packages, verify_picamera2
from exceptions import CameraError, StreamServerError
from logger import setup_logging, get_logger
from motion_detector import MotionDetector
from video_recorder import VideoRecorder, CircularVideoBuffer

# Set up logging first
setup_logging()
logger = get_logger(__name__)

# Check dependencies
check_and_install_packages()

# Import after dependency check
import cv2
import numpy as np

if not verify_picamera2():
    raise ImportError("Picamera2 is required but not available")

from picamera2 import Picamera2


class StreamingOutput(io.BufferedIOBase):
    """Thread-safe streaming output for video frames."""
    
    def __init__(self):
        """Initialize streaming output."""
        self.frame = None
        self.condition = Condition()
        self.last_frame_time = time.time()

    def write(self, buf):
        """Write frame data to the output buffer.
        
        Args:
            buf: Frame data bytes
            
        Returns:
            int: Number of bytes written
        """
        with self.condition:
            self.frame = buf
            self.last_frame_time = time.time()
            self.condition.notify_all()
        return len(buf)


class MotionStreamingOutput(StreamingOutput):
    """Enhanced streaming output with motion detection integration."""
    
    def __init__(self, config):
        """Initialize with motion detection capabilities.
        
        Args:
            config: Application configuration
        """
        super().__init__()
        
        # Initialize components
        self.config = config
        self.database = EventDatabase(config.database)
        self.motion_detector = MotionDetector(config.motion)
        self.circular_buffer = CircularVideoBuffer(config.video)
        self.video_recorder = VideoRecorder(config.video, self.database)
        
        # Processing state
        self.frame_count = 0
        self.motion_status = "No Motion"
        self.motion_processing_active = True
        self.latest_frame_for_processing = None
        
        # Start motion processing thread
        self.motion_thread = threading.Thread(
            target=self._motion_processing_loop, 
            daemon=True,
            name="MotionProcessor"
        )
        self.motion_thread.start()
        
        logger.info("🎥 Motion streaming output initialized")

    def write(self, buf):
        """Write frame and process for motion detection.
        
        Args:
            buf: Frame data bytes
            
        Returns:
            int: Number of bytes written
        """
        # Call parent write method
        result = super().write(buf)
        
        try:
            # Convert JPEG to numpy array for processing
            nparr = np.frombuffer(buf, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                self.frame_count += 1
                
                # Store latest frame for motion processing
                self.latest_frame_for_processing = frame.copy()
                
                # Add to circular buffer
                self.circular_buffer.add_frame(frame)
                
                # Add to recording if active
                if self.video_recorder.is_recording:
                    self.video_recorder.add_frame(frame)
                    
        except Exception as e:
            logger.error(f"❌ Error processing frame: {e}")
            
        return result

    def _motion_processing_loop(self):
        """Background thread for motion detection processing."""
        logger.info("🔄 Motion processing thread started")
        
        while self.motion_processing_active:
            try:
                if self.latest_frame_for_processing is not None:
                    frame = self.latest_frame_for_processing.copy()
                    self.latest_frame_for_processing = None
                    
                    # Detect motion
                    motion_detected = self.motion_detector.detect_motion(frame)
                    
                    if motion_detected:
                        self.motion_status = "Motion Detected!"
                        
                        # Start recording if not already recording
                        if not self.video_recorder.is_recording:
                            prebuffer_frames = self.circular_buffer.get_prebuffer_frames()
                            frame_size = (frame.shape[1], frame.shape[0])  # (width, height)
                            
                            if self.video_recorder.start_recording(prebuffer_frames, frame_size):
                                logger.info("🔴 Motion detected - recording started")
                    else:
                        self.motion_status = "No Motion"
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"❌ Motion processing error: {e}")
                time.sleep(0.1)  # Longer delay on error
                
        logger.info("🛑 Motion processing thread stopped")

    def stop_motion_processing(self):
        """Stop the motion processing thread."""
        self.motion_processing_active = False
        if self.motion_thread.is_alive():
            self.motion_thread.join(timeout=2.0)
            
        # Force stop any ongoing recording
        if self.video_recorder.is_recording:
            self.video_recorder.force_stop()


class StreamingHandler(server.BaseHTTPRequestHandler):
    """HTTP handler for video streaming."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._serve_html_page()
        elif self.path == '/stream.mjpg':
            self._serve_mjpeg_stream()
        elif self.path == '/favicon.ico':
            self._serve_favicon()
        else:
            self.send_error(404)

    def _serve_html_page(self):
        """Serve the main HTML page."""
        content = self._get_html_content()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def _serve_mjpeg_stream(self):
        """Serve the MJPEG video stream."""
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        
        try:
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                    
                if frame is None:
                    continue
                    
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
                
        except Exception as e:
            logger.warning(f"Client disconnected: {e}")

    def _serve_favicon(self):
        """Serve a simple favicon response."""
        self.send_response(204)  # No Content
        self.end_headers()

    def _get_html_content(self):
        """Get the HTML content for the main page."""
        self.end_headers()
        self.wfile.write(content)

    def _serve_mjpeg_stream(self) -> None:
        """Serve the MJPEG video stream."""
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        
        try:
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                    
                if frame is None:
                    continue
                    
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
                
        except Exception as e:
            logger.warning(f"Client disconnected: {e}")

    def _serve_favicon(self) -> None:
        """Serve a simple favicon response."""
        self.send_response(204)  # No Content
        self.end_headers()

    def _get_html_content(self) -> bytes:
        """Get the HTML content for the main page."""
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Motion Detection Stream Server</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .status-bar {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}
        .status-item {{
            text-align: center;
        }}
        .status-label {{
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }}
        .status-value {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        .camera-container {{
            text-align: center;
            background: rgba(0,0,0,0.3);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        .camera {{
            border-radius: 10px;
            border: 3px solid #00ff88;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
            max-width: 100%;
            height: auto;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Motion Detection Stream</h1>
        
        <div class="status-bar">
            <div class="status-item">
                <div class="status-label">Status</div>
                <div class="status-value">🟢 Active</div>
            </div>
            <div class="status-item">
                <div class="status-label">Motion</div>
                <div class="status-value" id="motion-status">Monitoring</div>
            </div>
            <div class="status-item">
                <div class="status-label">Recording</div>
                <div class="status-value" id="recording-status">Standby</div>
            </div>
        </div>
        
        <div class="camera-container">
            <img src="/stream.mjpg" class="camera" alt="Video Stream">
        </div>
        
        <div class="footer">
            <p>Motion Detection Stream Server v2.0</p>
            <p>High-performance video streaming with OpenCV motion detection</p>
        </div>
    </div>
</body>
</html>'''
        return html.encode('utf-8')

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"HTTP: {format % args}")


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """Multi-threaded HTTP server for video streaming."""
    
    allow_reuse_address = True
    daemon_threads = True


class StreamWatchdog:
    """Monitors stream health and handles recovery."""
    
    def __init__(self, timeout=10.0):
        """Initialize watchdog.
        
        Args:
            timeout: Timeout in seconds for stream health check
        """
        self.timeout = timeout
        self.is_running = True
        
    def is_stream_healthy(self, output):
        """Check if the stream is healthy.
        
        Args:
            output: Streaming output to check
            
        Returns:
            bool: True if stream is healthy
        """
        if not self.is_running:
            return False
            
        time_since_last_frame = time.time() - output.last_frame_time
        return time_since_last_frame < self.timeout
        
    def stop(self):
        """Stop the watchdog."""
        self.is_running = False


def initialize_camera(config):
    """Initialize and configure the camera.
    
    Args:
        config: Application configuration
        
    Returns:
        Picamera2: Configured camera instance
        
    Raises:
        CameraError: If camera initialization fails
    """
    try:
        picam2 = Picamera2()
        
        # Configure camera
        video_config = picam2.create_video_configuration(
            main={"size": config.camera.resolution, "format": config.camera.format}
        )
        picam2.configure(video_config)
        
        logger.info(f"✅ Camera initialized: {config.camera.resolution}")
        return picam2
        
    except Exception as e:
        logger.error(f"❌ Camera initialization failed: {e}")
        raise CameraError(f"Failed to initialize camera: {e}")


def start_recording_with_recovery(picam2, output):
    """Start recording with error recovery.
    
    Args:
        picam2: Camera instance
        output: Streaming output
        
    Returns:
        bool: True if recording started successfully
    """
    try:
        picam2.start_recording(output, format='mjpeg')
        logger.info("✅ Camera recording started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start recording: {e}")
        return False


def monitor_stream_health(watchdog, picam2, output):
    """Monitor stream health and recover if needed.
    
    Args:
        watchdog: Stream watchdog instance
        picam2: Camera instance
        output: Streaming output
    """
    consecutive_failures = 0
    
    while watchdog.is_running:
        time.sleep(5)  # Check every 5 seconds
        
        if not watchdog.is_stream_healthy(output):
            consecutive_failures += 1
            logger.warning(f"⚠️ Stream health check failed (attempt {consecutive_failures})")
            
            try:
                # Stop and restart recording
                picam2.stop_recording()
                time.sleep(1)
                
                if start_recording_with_recovery(picam2, output):
                    logger.info("✅ Stream recovery successful")
                    consecutive_failures = 0
                else:
                    logger.error("❌ Stream recovery failed")
                    
            except Exception as e:
                logger.error(f"❌ Recovery attempt failed: {e}")
                
            if consecutive_failures >= 3:
                logger.critical("🚨 Multiple stream recovery failures - manual intervention required")
                
        else:
            if consecutive_failures > 0:
                logger.info("✅ Stream health restored")
                consecutive_failures = 0


def run_stream_server():
    """Main server loop with motion detection."""
    global output
    
    config = AppConfig()
    restart_count = 0
    
    while True:
        try:
            restart_count += 1
            logger.info(f"🚀 Starting motion detection stream server (attempt #{restart_count})")
            
            # Initialize camera
            picam2 = initialize_camera(config)
            
            try:
                # Initialize motion detection output
                output = MotionStreamingOutput(config)
                
                # Initialize stream watchdog
                watchdog = StreamWatchdog()
                
                logger.info("🔍 Motion detection system initialized")
                logger.info("📊 Configuration:")
                logger.info(f"   - Motion threshold: {config.motion.threshold}")
                logger.info(f"   - Minimum area: {config.motion.min_area} pixels")
                logger.info(f"   - Pre-record buffer: {config.video.pre_buffer_duration} seconds")
                logger.info(f"   - Post-motion recording: {config.video.post_motion_duration} seconds")
                logger.info(f"   - Recording FPS: {config.video.fps}")
                logger.info(f"   - Recording directory: {config.video.output_dir}")
                logger.info(f"   - Database: {config.database.db_path}")
                logger.info(f"   - Video format: motion_YYYYMMDD_HHMMSS.mp4")
                
                # Start recording
                if not start_recording_with_recovery(picam2, output):
                    raise StreamServerError("Failed to start recording")
                
                # Start health monitoring in separate thread
                watchdog_thread = threading.Thread(
                    target=monitor_stream_health, 
                    args=(watchdog, picam2, output),
                    daemon=True,
                    name="StreamWatchdog"
                )
                watchdog_thread.start()
                
                # Start HTTP server
                address = (config.server.host, config.server.port)
                server_instance = StreamingServer(address, StreamingHandler)
                
                logger.info(f"🌐 Server started on http://localhost:{config.server.port}")
                logger.info("🎥 Motion detection is ACTIVE - recordings will be saved automatically")
                logger.info("📊 Web interface available for monitoring")
                
                try:
                    server_instance.serve_forever()
                finally:
                    logger.info("🛑 Shutting down server...")
                    watchdog.stop()
                    output.stop_motion_processing()
                    server_instance.shutdown()
                    
            finally:
                try:
                    picam2.stop_recording()
                    picam2.close()
                    logger.info("📹 Camera closed")
                except Exception as e:
                    logger.error(f"❌ Error closing camera: {e}")
                    
        except KeyboardInterrupt:
            logger.info("👋 Received shutdown signal")
            break
        except Exception as e:
            logger.error(f"💥 Server error: {e}")
            if restart_count >= 3:
                logger.critical("🚨 Too many restart attempts - exiting")
                break
            logger.info(f"🔄 Restarting in 5 seconds... (attempt {restart_count + 1})")
            time.sleep(5)


def main():
    """Main entry point."""
    try:
        logger.info("🎬 Motion Detection Stream Server v2.0 Starting...")
        run_stream_server()
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        raise
    finally:
        logger.info("👋 Motion Detection Stream Server stopped")


if __name__ == "__main__":
    main()