#!/usr/bin/env python3
"""
Simple MJPEG Stream Server

A minimal video streaming server for Raspberry Pi camera.
Serves only the raw video stream without any analysis or recording.
"""

import io
import socketserver
import threading
import time
from http import server
from threading import Condition

# Local imports
from config import AppConfig
from dependencies import verify_picamera2
from exceptions import CameraError
from logger import setup_logging, get_logger

# Set up logging first
setup_logging()
logger = get_logger(__name__)

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

    def write(self, buf):
        """Write frame data to the output buffer.
        
        Args:
            buf: Frame data bytes
            
        Returns:
            int: Number of bytes written
        """
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    """HTTP handler for video streaming."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/stream.mjpg':
            self._serve_mjpeg_stream()
        else:
            self.send_error(404)

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

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"HTTP: {format % args}")


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """Multi-threaded HTTP server for video streaming."""
    
    allow_reuse_address = True
    daemon_threads = True


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


def start_camera_streaming(picam2, output):
    """Start camera streaming.
    
    Args:
        picam2: Camera instance
        output: Streaming output
        
    Returns:
        bool: True if camera started successfully
    """
    try:
        if output is None:
            logger.error("❌ Output is None - cannot start camera")
            return False
        
        logger.info("🔧 Starting camera streaming")
        picam2.start()
        
        # Start frame capture thread
        def capture_frames():
            """Capture frames and send to output."""
            try:
                import cv2  # Import only when needed for JPEG encoding
            except ImportError:
                logger.error("❌ OpenCV required for JPEG encoding")
                return
                
            while True:
                try:
                    # Capture JPEG frame
                    frame_data = picam2.capture_array("main")
                    if frame_data is not None:
                        # Convert to JPEG
                        _, jpeg_data = cv2.imencode('.jpg', frame_data)
                        # Send to output
                        output.write(jpeg_data.tobytes())
                    time.sleep(1/30)  # 30 FPS
                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    break
        
        # Start capture thread
        capture_thread = threading.Thread(target=capture_frames, daemon=True)
        capture_thread.start()
        
        logger.info("✅ Camera streaming started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start camera: {e}")
        return False


def run_stream_server():
    """Main server loop for simple streaming."""
    global output
    
    config = AppConfig()
    restart_count = 0
    
    while True:
        try:
            restart_count += 1
            logger.info(f"🚀 Starting simple stream server (attempt #{restart_count})")
            
            # Initialize camera
            picam2 = initialize_camera(config)
            
            try:
                # Initialize simple streaming output
                output = StreamingOutput()
                logger.info("🔧 Created simple streaming output")
                
                logger.info("📊 Configuration:")
                logger.info(f"   - Camera resolution: {config.camera.resolution}")
                logger.info(f"   - Server port: {config.server.port}")
                
                # Start streaming
                if not start_camera_streaming(picam2, output):
                    raise CameraError("Failed to start streaming")
                
                # Start HTTP server
                address = (config.server.host, config.server.port)
                server_instance = StreamingServer(address, StreamingHandler)
                
                logger.info(f"🌐 Simple stream server started on http://localhost:{config.server.port}/stream.mjpg")
                logger.info("📹 Direct MJPEG stream available")
                
                try:
                    server_instance.serve_forever()
                finally:
                    logger.info("🛑 Shutting down server...")
                    server_instance.shutdown()
                    
            finally:
                try:
                    picam2.stop()
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
        logger.info("🎬 Simple MJPEG Stream Server Starting...")
        run_stream_server()
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        raise
    finally:
        logger.info("👋 Simple Stream Server stopped")


if __name__ == "__main__":
    main()