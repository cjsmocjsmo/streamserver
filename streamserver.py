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
        super().__init__()
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
        try:
            # Convert JPEG to numpy array for processing
            nparr = np.frombuffer(buf, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                self.frame_count += 1
                
                # Detect motion and get bounding boxes
                motion_detected, motion_boxes = self.motion_detector.detect_motion(frame)
                
                # Draw motion detection boxes on frame
                display_frame = frame.copy()
                if motion_detected and motion_boxes:
                    for (x, y, w, h) in motion_boxes:
                        # Draw green rectangle around motion area
                        cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        # Add motion label
                        cv2.putText(display_frame, "MOTION", (x, y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Handle motion detection results
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
                
                # Add original frame to circular buffer and recording
                self.circular_buffer.add_frame(frame)
                if self.video_recorder.is_recording:
                    self.video_recorder.add_frame(frame)
                
                # Convert display frame (with boxes) back to JPEG for streaming
                _, jpeg_data = cv2.imencode('.jpg', display_frame)
                
                # Call parent write method with the annotated frame
                with self.condition:
                    self.frame = jpeg_data.tobytes()
                    self.last_frame_time = time.time()
                    self.condition.notify_all()
                    
                return len(jpeg_data.tobytes())
                    
        except Exception as e:
            logger.error(f"❌ Frame processing error: {e}")
            # Fallback to original behavior
            return super().write(buf)

    def _motion_processing_loop(self):
        """Motion processing loop - simplified since detection moved to write method."""
        logger.info("🔄 Motion processing thread started")
        
        # Keep thread alive but motion detection now happens in write() method
        while self.motion_processing_active:
            time.sleep(1)  # Just keep thread alive
                
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
    
    # Class variable to store output instance for database access
    output_instance = None
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._serve_html_page()
        elif self.path == '/stream.mjpg':
            self._serve_mjpeg_stream()
        elif self.path == '/api/events/count':
            self._serve_event_count_json()
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

    def _serve_event_count_json(self):
        """Serve event count as JSON for AJAX requests."""
        try:
            # Get event count from database
            event_count = 0
            if self.output_instance and hasattr(self.output_instance, 'database'):
                event_count = self.output_instance.database.get_event_count()
            
            # Create JSON response
            json_data = f'{{"count": {event_count}}}'
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS if needed
            self.send_header('Content-Length', len(json_data))
            self.end_headers()
            self.wfile.write(json_data.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"❌ Error serving event count JSON: {e}")
            # Send error response
            error_json = '{"count": 0, "error": "Failed to get count"}'
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error_json))
            self.end_headers()
            self.wfile.write(error_json.encode('utf-8'))

    def _get_html_content(self) -> bytes:
        """Get the HTML content for the main page."""
        # Get event count from database
        event_count = 0
        if self.output_instance and hasattr(self.output_instance, 'database'):
            event_count = self.output_instance.database.get_event_count()
        
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
        <div class="camera-container">
            <img src="/stream.mjpg" class="camera" alt="Video Stream">
        </div>
        
        <div class="footer">
            <p>Motion Detection Stream Server v2.0</p>
            <p>Events: <span class="numbevents">{event_count}</span></p>
        </div>
    </div>

    <script>
        // Function to update event count
        async function updateEventCount() {{
            try {{
                const response = await fetch('/api/events/count');
                if (response.ok) {{
                    const data = await response.json();
                    const countElement = document.querySelector('.numbevents');
                    if (countElement) {{
                        countElement.textContent = data.count;
                    }}
                }} else {{
                    console.error('Failed to fetch event count:', response.status);
                }}
            }} catch (error) {{
                console.error('Error updating event count:', error);
            }}
        }}

        // Update event count every 30 seconds
        setInterval(updateEventCount, 30000);

        // Also update on page load after a short delay to ensure DOM is ready
        window.addEventListener('DOMContentLoaded', function() {{
            setTimeout(updateEventCount, 1000);
        }});
    </script>
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


def start_camera_with_recovery(picam2, output):
    """Start camera with error recovery.
    
    Args:
        picam2: Camera instance
        output: Streaming output (not used with start() method)
        
    Returns:
        bool: True if camera started successfully
    """
    try:
        if output is None:
            logger.error("❌ Output is None - cannot start camera")
            return False
        
        logger.info(f"🔧 Starting camera with output: {type(output)}")
        # Start camera for streaming
        picam2.start()
        
        # Start frame capture thread to feed our output
        def capture_frames():
            """Capture frames and send to output."""
            while True:
                try:
                    # Capture JPEG frame
                    frame_data = picam2.capture_array("main")
                    if frame_data is not None:
                        # Convert to JPEG
                        _, jpeg_data = cv2.imencode('.jpg', frame_data)
                        # Send to our output
                        output.write(jpeg_data.tobytes())
                    time.sleep(1/30)  # 30 FPS
                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    break
        
        # Start capture thread
        capture_thread = threading.Thread(target=capture_frames, daemon=True)
        capture_thread.start()
        
        logger.info("✅ Camera started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start camera: {e}")
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
                
                if start_camera_with_recovery(picam2, output):
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
                try:
                    output = MotionStreamingOutput(config)
                    logger.info(f"🔧 Created output object: {type(output)}")
                except Exception as e:
                    logger.error(f"❌ Failed to create output object: {e}")
                    raise StreamServerError(f"Failed to create output object: {e}")
                
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
                logger.info(f"🔧 About to start recording with output: {output}")
                if not start_camera_with_recovery(picam2, output):
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
                
                # Set output instance for database access in handler
                StreamingHandler.output_instance = output
                
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