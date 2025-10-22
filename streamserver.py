import io
import logging
import socketserver
import time
import threading
from threading import Condition
from http import server

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PAGE = """\
<html>
<head>
<title>Raspberry Pi MJPEG Stream</title>
</head>
<body>
<h1>Raspberry Pi MJPEG Stream</h1>
<div class="camera">
    <img src="stream.mjpg" width="640" height="480" />
</div>
</body>
</html>
<style>
    body {
        background:black;
    }
    h1 {
        text-align: center;
        color: green;
    }
    .camera {
        display: flex;
        justify-content: center;
        align-items: center;
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
    """Main server loop with recovery"""
    restart_count = 0
    
    while True:
        try:
            restart_count += 1
            logging.info(f"Starting stream server (attempt #{restart_count})")
            
            # Initialize camera
            picam2 = initialize_camera()
            
            try:
                # Create output and watchdog
                global output
                output = StreamingOutput()
                watchdog = StreamWatchdog()
                
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
                
                try:
                    server.serve_forever()
                finally:
                    watchdog.stop()
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
