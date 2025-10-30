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
        self._frame_count = 0

    def write(self, buf):
        """Write frame data to the output buffer.
        
        Args:
            buf: Frame data bytes
            
        Returns:
            int: Number of bytes written
        """
        try:
            with self.condition:
                self.frame = buf
                self._frame_count += 1
                self.condition.notify_all()
            return len(buf)
        except Exception as e:
            logger.error(f"❌ Error writing frame data: {e}", exc_info=True)
            raise CameraError(f"Frame write failed: {e}")


class StreamingHandler(server.BaseHTTPRequestHandler):
    """HTTP handler for video streaming."""
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            logger.debug(f"🌐 Handling GET request: {self.path}")
            if self.path == '/stream.mjpg':
                self._serve_mjpeg_stream()
            else:
                logger.warning(f"⚠️ 404 - Path not found: {self.path}")
                self.send_error(404)
        except Exception as e:
            logger.error(f"❌ Error handling GET request for {self.path}: {e}", exc_info=True)
            try:
                self.send_error(500)
            except Exception as send_error_exc:
                logger.error(f"❌ Failed to send error response: {send_error_exc}", exc_info=True)

    def _serve_mjpeg_stream(self):
        """Serve the MJPEG video stream."""
        frame_count = 0  # Initialize at the start to avoid UnboundLocalError
        try:
            logger.debug("🎥 Starting MJPEG stream serve")
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            
            try:
                while True:
                    try:
                        with output.condition:
                            output.condition.wait(timeout=5.0)  # Add timeout to prevent hanging
                            frame = output.frame
                            
                        if frame is None:
                            logger.debug("🔄 No frame available, continuing...")
                            continue
                            
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(frame))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                        
                        frame_count += 1
                        if frame_count % 100 == 0:  # Log every 100 frames
                            logger.debug(f"📊 Streamed {frame_count} frames")
                            
                    except Exception as frame_error:
                        logger.error(f"❌ Error processing frame {frame_count}: {frame_error}", exc_info=True)
                        break
                        
            except Exception as stream_error:
                logger.error(f"❌ Stream serving error after {frame_count} frames: {stream_error}", exc_info=True)
                
        except Exception as e:
            logger.error(f"❌ Critical error in MJPEG stream setup: {e}", exc_info=True)
        finally:
            logger.info(f"🛑 MJPEG stream ended (served {frame_count} frames)")

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
        logger.info("📷 Initializing Picamera2...")
        picam2 = Picamera2()
        
        try:
            # Configure camera
            logger.debug(f"📐 Creating video configuration for {config.camera.resolution}")
            video_config = picam2.create_video_configuration(
                main={"size": config.camera.resolution, "format": config.camera.format}
            )
            
            logger.debug("🔧 Configuring camera with video config")
            picam2.configure(video_config)
            
            logger.info(f"✅ Camera initialized: {config.camera.resolution}")
            return picam2
            
        except Exception as config_error:
            logger.error(f"❌ Camera configuration failed: {config_error}", exc_info=True)
            raise CameraError(f"Failed to configure camera: {config_error}")
        
    except Exception as e:
        logger.error(f"❌ Camera initialization failed: {e}", exc_info=True)
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
        try:
            picam2.start()
            logger.debug("✅ Camera started successfully")
        except Exception as start_error:
            logger.error(f"❌ Failed to start camera: {start_error}", exc_info=True)
            return False
        
        # Start frame capture thread
        def capture_frames():
            """Capture frames and send to output."""
            try:
                try:
                    import cv2  # Import only when needed for JPEG encoding
                    logger.debug("📦 OpenCV imported for JPEG encoding")
                except ImportError as import_error:
                    logger.error(f"❌ OpenCV required for JPEG encoding: {import_error}", exc_info=True)
                    raise CameraError(f"OpenCV import failed: {import_error}")
                    
                frame_count = 0
                consecutive_errors = 0
                max_consecutive_errors = 10  # Restart camera after 10 consecutive errors
                
                while True:
                    try:
                        # Capture JPEG frame
                        frame_data = picam2.capture_array("main")
                        if frame_data is not None:
                            try:
                                # Convert to JPEG
                                _, jpeg_data = cv2.imencode('.jpg', frame_data)
                                # Send to output
                                output.write(jpeg_data.tobytes())
                                
                                frame_count += 1
                                consecutive_errors = 0  # Reset error counter on successful frame
                                
                                if frame_count % 300 == 0:  # Log every 300 frames (10 seconds at 30fps)
                                    logger.debug(f"📸 Captured {frame_count} frames")
                                    
                            except Exception as encode_error:
                                consecutive_errors += 1
                                logger.error(f"❌ Frame encoding error at frame {frame_count} (consecutive errors: {consecutive_errors}): {encode_error}", exc_info=True)
                                if consecutive_errors >= max_consecutive_errors:
                                    raise CameraError(f"Too many consecutive encoding errors ({consecutive_errors})")
                        else:
                            consecutive_errors += 1
                            logger.warning(f"⚠️ No frame data received (consecutive errors: {consecutive_errors})")
                            if consecutive_errors >= max_consecutive_errors:
                                raise CameraError(f"Too many consecutive null frames ({consecutive_errors})")
                                
                        time.sleep(1/30)  # 30 FPS
                        
                    except CameraError:
                        # Re-raise camera errors to trigger restart
                        raise
                    except Exception as capture_error:
                        consecutive_errors += 1
                        logger.error(f"❌ Frame capture error at frame {frame_count} (consecutive errors: {consecutive_errors}): {capture_error}", exc_info=True)
                        if consecutive_errors >= max_consecutive_errors:
                            raise CameraError(f"Too many consecutive capture errors ({consecutive_errors})")
                        time.sleep(0.1)  # Brief pause before retry
                        
            except CameraError:
                # Re-raise camera errors to trigger restart
                raise
            except Exception as thread_error:
                logger.error(f"❌ Capture thread error: {thread_error}", exc_info=True)
                raise CameraError(f"Capture thread failed: {thread_error}")
        
        try:
            # Start capture thread
            capture_thread = threading.Thread(target=capture_frames, daemon=True)
            capture_thread.start()
            logger.info("✅ Camera streaming started with capture thread")
            return True
            
        except Exception as thread_start_error:
            logger.error(f"❌ Failed to start capture thread: {thread_start_error}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to start camera streaming: {e}", exc_info=True)
        return False


def run_stream_server():
    """Main server loop for simple streaming."""
    global output
    
    config = AppConfig()
    restart_count = 0
    max_restarts = 10  # Allow more restarts for camera errors
    
    while True:
        picam2 = None
        server_instance = None
        
        try:
            restart_count += 1
            logger.info(f"🚀 Starting simple stream server (attempt #{restart_count})")
            
            # Initialize camera with retry logic
            camera_retry_count = 0
            max_camera_retries = 3
            
            while camera_retry_count < max_camera_retries:
                try:
                    camera_retry_count += 1
                    logger.debug(f"🔄 Camera initialization attempt {camera_retry_count}/{max_camera_retries}")
                    picam2 = initialize_camera(config)
                    logger.debug("✅ Camera initialization completed")
                    break
                except Exception as camera_init_error:
                    logger.error(f"❌ Camera initialization failed (attempt {camera_retry_count}/{max_camera_retries}): {camera_init_error}", exc_info=True)
                    if camera_retry_count >= max_camera_retries:
                        raise CameraError(f"Camera initialization failed after {max_camera_retries} attempts")
                    logger.info(f"⏳ Retrying camera initialization in 3 seconds...")
                    time.sleep(3)
            
            try:
                # Initialize simple streaming output
                output = StreamingOutput()
                logger.info("🔧 Created simple streaming output")
                
                logger.info("📊 Configuration:")
                logger.info(f"   - Camera resolution: {config.camera.resolution}")
                logger.info(f"   - Server port: {config.server.port}")
                
            except Exception as output_error:
                logger.error(f"❌ Failed to create streaming output: {output_error}", exc_info=True)
                raise CameraError(f"Streaming output creation failed: {output_error}")
                
            # Start streaming with retry logic
            streaming_retry_count = 0
            max_streaming_retries = 3
            
            while streaming_retry_count < max_streaming_retries:
                try:
                    streaming_retry_count += 1
                    logger.debug(f"🔄 Camera streaming attempt {streaming_retry_count}/{max_streaming_retries}")
                    if not start_camera_streaming(picam2, output):
                        raise CameraError("Failed to start streaming")
                    logger.debug("✅ Camera streaming started successfully")
                    break
                except Exception as streaming_error:
                    logger.error(f"❌ Camera streaming failed (attempt {streaming_retry_count}/{max_streaming_retries}): {streaming_error}", exc_info=True)
                    if streaming_retry_count >= max_streaming_retries:
                        raise CameraError(f"Camera streaming failed after {max_streaming_retries} attempts")
                    logger.info(f"⏳ Retrying camera streaming in 2 seconds...")
                    time.sleep(2)
                
            # Start HTTP server
            try:
                address = (config.server.host, config.server.port)
                logger.debug(f"🌐 Creating server on {address}")
                server_instance = StreamingServer(address, StreamingHandler)
                
                logger.info(f"🌐 Simple stream server started on http://localhost:{config.server.port}/stream.mjpg")
                logger.info("📹 Direct MJPEG stream available")
                
                try:
                    logger.debug("🔄 Starting server loop...")
                    server_instance.serve_forever()
                    
                except Exception as serve_error:
                    logger.error(f"❌ Server serving error: {serve_error}", exc_info=True)
                    # Don't raise here - let the outer exception handler restart everything
                    
                finally:
                    logger.info("🛑 Shutting down server...")
                    try:
                        if server_instance:
                            server_instance.shutdown()
                            logger.debug("✅ Server shutdown completed")
                    except Exception as shutdown_error:
                        logger.error(f"❌ Server shutdown error: {shutdown_error}", exc_info=True)
                        
            except Exception as server_error:
                logger.error(f"❌ HTTP server creation/start failed: {server_error}", exc_info=True)
                raise CameraError(f"HTTP server failed: {server_error}")
                    
        except KeyboardInterrupt:
            logger.info("� Received shutdown signal")
            break
        except CameraError as camera_error:
            logger.error(f"🔄 Camera error - restarting: {camera_error}", exc_info=True)
            if restart_count >= max_restarts:
                logger.critical(f"🚨 Too many camera restart attempts ({restart_count}/{max_restarts}) - exiting")
                break
            logger.info(f"� Restarting camera and server in 5 seconds... (attempt {restart_count + 1})")
            time.sleep(5)
        except Exception as e:
            logger.error(f"💥 Unexpected server error - restarting: {e}", exc_info=True)
            if restart_count >= max_restarts:
                logger.critical(f"🚨 Too many restart attempts ({restart_count}/{max_restarts}) - exiting")
                break
            logger.info(f"🔄 Restarting in 5 seconds... (attempt {restart_count + 1})")
            time.sleep(5)
        finally:
            # Always cleanup camera and server resources
            if picam2:
                try:
                    logger.debug("🔄 Stopping camera...")
                    picam2.stop()
                    picam2.close()
                    logger.info("📹 Camera closed")
                except Exception as camera_close_error:
                    logger.error(f"❌ Error closing camera: {camera_close_error}", exc_info=True)
                    
            if server_instance:
                try:
                    server_instance.server_close()
                    logger.debug("🌐 Server socket closed")
                except Exception as socket_close_error:
                    logger.error(f"❌ Error closing server socket: {socket_close_error}", exc_info=True)


def main():
    """Main entry point."""
    try:
        logger.info("🎬 Simple MJPEG Stream Server Starting...")
        run_stream_server()
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        raise
    except KeyboardInterrupt:
        logger.info("👋 Interrupted by user")
    finally:
        logger.info("👋 Simple Stream Server stopped")


if __name__ == "__main__":
    main()