#!/usr/bin/env python3
"""
RTSP Stream Server

A hardware-accelerated RTSP streaming server for Raspberry Pi camera.
Uses Picamera2 with H.264 hardware encoding for efficient streaming.
Optimized for Pi 3B+ with support for 2-4 concurrent clients.
"""

import io
import socket
import threading
import time
import struct
import random
from threading import Condition, Event

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
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput


class H264StreamOutput(io.BufferedIOBase):
    """Thread-safe H.264 streaming output with NAL unit parsing."""
    
    def __init__(self):
        """Initialize H.264 streaming output."""
        super().__init__()
        self.clients = []
        self.condition = Condition()
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.is_healthy = True
        self.sps = None  # Sequence Parameter Set
        self.pps = None  # Picture Parameter Set
        self.current_nal = b''
        self.buffer = b''

    def add_client(self, client):
        """Add a client to receive H.264 stream."""
        with self.condition:
            self.clients.append(client)
            logger.debug(f"📱 Client added. Total clients: {len(self.clients)}")
            
            # Send SPS/PPS to new client if available
            if self.sps and self.pps:
                try:
                    client.send_h264_data(self.sps)
                    client.send_h264_data(self.pps)
                    logger.debug("📦 Sent SPS/PPS to new client")
                except Exception as e:
                    logger.debug(f"⚠️ Failed to send SPS/PPS to new client: {e}")

    def remove_client(self, client):
        """Remove a client from the stream."""
        with self.condition:
            if client in self.clients:
                self.clients.remove(client)
                logger.debug(f"📱 Client removed. Total clients: {len(self.clients)}")

    def write(self, data):
        """Write H.264 data and distribute to clients."""
        try:
            self.buffer += data
            self._process_nal_units()
            
            with self.condition:
                self.last_frame_time = time.time()
                self.frame_count += 1
                self.is_healthy = True
                
            return len(data)
        except Exception as e:
            logger.error(f"❌ Error writing H.264 data: {e}", exc_info=True)
            self.is_healthy = False
            raise CameraError(f"H.264 write failed: {e}")

    def _process_nal_units(self):
        """Process NAL units from the buffer."""
        while len(self.buffer) >= 4:
            # Look for NAL unit start code (0x00000001)
            start_code_pos = self.buffer.find(b'\x00\x00\x00\x01')
            if start_code_pos == -1:
                # No start code found, keep last 3 bytes in buffer
                self.buffer = self.buffer[-3:]
                break
                
            if start_code_pos > 0:
                # Found start code, but not at beginning - skip invalid data
                self.buffer = self.buffer[start_code_pos:]
                continue
                
            # Look for next start code to determine NAL unit length
            next_start = self.buffer.find(b'\x00\x00\x00\x01', 4)
            if next_start == -1:
                # No complete NAL unit yet
                break
                
            # Extract complete NAL unit
            nal_unit = self.buffer[4:next_start]
            self.buffer = self.buffer[next_start:]
            
            if nal_unit:
                self._handle_nal_unit(nal_unit)

    def _handle_nal_unit(self, nal_unit):
        """Handle a complete NAL unit."""
        if not nal_unit:
            return
            
        nal_type = nal_unit[0] & 0x1f
        
        # Store SPS and PPS for new clients
        if nal_type == 7:  # SPS
            self.sps = b'\x00\x00\x00\x01' + nal_unit
            logger.debug("📦 Stored SPS")
        elif nal_type == 8:  # PPS
            self.pps = b'\x00\x00\x00\x01' + nal_unit
            logger.debug("📦 Stored PPS")
        
        # Send to all clients
        complete_nal = b'\x00\x00\x00\x01' + nal_unit
        clients_to_remove = []
        
        with self.condition:
            for client in self.clients[:]:  # Copy list to avoid modification during iteration
                try:
                    client.send_h264_data(complete_nal)
                except Exception as e:
                    logger.debug(f"📱 Client disconnected: {e}")
                    clients_to_remove.append(client)
            
            # Remove disconnected clients
            for client in clients_to_remove:
                if client in self.clients:
                    self.clients.remove(client)

    def check_stream_health(self, max_frame_age=10.0):
        """Check if the stream is healthy."""
        if not self.is_healthy:
            return False
            
        frame_age = time.time() - self.last_frame_time
        if frame_age > max_frame_age:
            logger.warning(f"⚠️ Stream unhealthy: No frames for {frame_age:.1f}s")
            return False
            
        return True
    
    def get_stream_stats(self):
        """Get current stream statistics."""
        frame_age = time.time() - self.last_frame_time
        return {
            'frame_count': self.frame_count,
            'last_frame_age': frame_age,
            'is_healthy': self.is_healthy,
            'client_count': len(self.clients)
        }

    # Required BufferedIOBase methods
    def readable(self):
        """Return whether object was opened for reading."""
        return False  # This is a write-only stream

    def writable(self):
        """Return whether object was opened for writing."""
        return True

    def seekable(self):
        """Return whether object supports random access."""
        return False  # Streaming data, no seeking

    def close(self):
        """Close the stream and cleanup."""
        with self.condition:
            self.clients.clear()
            self.is_healthy = False

    def flush(self):
        """Flush write buffers (no-op for streaming)."""
        pass


class StreamMonitor:
    """Monitors video stream health and triggers restarts on failures."""
    
    def __init__(self, output, restart_callback, check_interval=5.0, max_frame_age=10.0):
        """Initialize stream monitor."""
        self.output = output
        self.restart_callback = restart_callback
        self.check_interval = check_interval
        self.max_frame_age = max_frame_age
        self.is_running = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start the stream monitoring thread."""
        if self.is_running:
            logger.warning("⚠️ Stream monitor already running")
            return
            
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"📊 Stream monitor started (check interval: {self.check_interval}s, max frame age: {self.max_frame_age}s)")
        
    def stop_monitoring(self):
        """Stop the stream monitoring thread."""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.info("🛑 Stopping stream monitor...")
            
    def _monitor_loop(self):
        """Main monitoring loop."""
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while self.is_running:
            try:
                time.sleep(self.check_interval)
                
                if not self.is_running:
                    break
                    
                # Check stream health
                is_healthy = self.output.check_stream_health(self.max_frame_age)
                stats = self.output.get_stream_stats()
                
                if is_healthy:
                    consecutive_failures = 0
                    if stats['frame_count'] % 600 == 0 and stats['frame_count'] > 0:  # Log every 600 frames
                        logger.debug(f"📊 Stream healthy: {stats['frame_count']} frames, {stats['client_count']} clients, last frame {stats['last_frame_age']:.1f}s ago")
                else:
                    consecutive_failures += 1
                    logger.error(f"❌ Stream unhealthy (failure #{consecutive_failures}): {stats}")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.critical(f"🚨 Stream failed {consecutive_failures} consecutive checks - triggering restart")
                        self.restart_callback("Stream health check failed")
                        break
                        
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"❌ Stream monitor error (failure #{consecutive_failures}): {e}", exc_info=True)
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.critical(f"🚨 Stream monitor failed {consecutive_failures} times - triggering restart")
                    self.restart_callback("Stream monitor error")
                    break
        
        logger.info("🛑 Stream monitor stopped")


class RTSPSession:
    """Represents an RTSP client session."""
    
    def __init__(self, client_socket, session_id):
        """Initialize RTSP session."""
        self.socket = client_socket
        self.session_id = session_id
        self.rtp_port = None
        self.rtcp_port = None
        self.rtp_socket = None
        self.rtcp_socket = None
        self.sequence_number = random.randint(0, 65535)
        self.timestamp = 0
        self.ssrc = random.randint(0, 0xFFFFFFFF)
        self.is_playing = False
        self.client_addr = client_socket.getpeername()
        
    def send_h264_data(self, h264_data):
        """Send H.264 data via RTP."""
        if not self.is_playing or not self.rtp_socket:
            return
            
        try:
            # Create RTP packet
            rtp_packet = self._create_rtp_packet(h264_data)
            self.rtp_socket.sendto(rtp_packet, (self.client_addr[0], self.rtp_port))
            self.sequence_number = (self.sequence_number + 1) % 65536
            self.timestamp += 3600  # 90kHz clock for 25fps
        except Exception as e:
            logger.debug(f"📱 RTP send failed for session {self.session_id}: {e}")
            raise

    def _create_rtp_packet(self, payload):
        """Create RTP packet with H.264 payload."""
        # RTP Header (12 bytes)
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 1  # Mark end of frame
        payload_type = 96  # Dynamic payload type for H.264
        
        header = struct.pack(
            '!BBHII',
            (version << 6) | (padding << 5) | (extension << 4) | cc,
            (marker << 7) | payload_type,
            self.sequence_number,
            self.timestamp,
            self.ssrc
        )
        
        return header + payload

    def close(self):
        """Close the session and cleanup resources."""
        try:
            if self.rtp_socket:
                self.rtp_socket.close()
                self.rtp_socket = None
            if self.rtcp_socket:
                self.rtcp_socket.close()
                self.rtcp_socket = None
            if self.socket:
                self.socket.close()
                self.socket = None
        except Exception as e:
            logger.debug(f"Session cleanup error: {e}")


class RTSPHandler:
    """RTSP request handler."""
    
    def __init__(self, socket_conn, client_address, stream_output):
        """Initialize RTSP handler."""
        self.socket = socket_conn
        self.client_address = client_address
        self.stream_output = stream_output
        self.session = None
        self.cseq = 0
        
    def handle_request(self):
        """Handle RTSP requests."""
        try:
            while True:
                # Receive request
                data = self.socket.recv(4096)
                if not data:
                    break
                    
                request = data.decode('utf-8', errors='ignore')
                logger.debug(f"📡 RTSP Request from {self.client_address}: {request.split()[0] if request.split() else 'EMPTY'}")
                
                # Parse request
                lines = request.strip().split('\r\n')
                if not lines:
                    continue
                    
                request_line = lines[0]
                headers = {}
                
                for line in lines[1:]:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip().lower()] = value.strip()
                
                # Extract CSeq
                self.cseq = int(headers.get('cseq', '0'))
                
                # Handle different RTSP methods
                if request_line.startswith('OPTIONS'):
                    self._handle_options()
                elif request_line.startswith('DESCRIBE'):
                    self._handle_describe(request_line)
                elif request_line.startswith('SETUP'):
                    self._handle_setup(headers)
                elif request_line.startswith('PLAY'):
                    self._handle_play()
                elif request_line.startswith('TEARDOWN'):
                    self._handle_teardown()
                    break
                else:
                    self._send_response(501, "Not Implemented")
                    
        except Exception as e:
            logger.debug(f"📱 RTSP handler error for {self.client_address}: {e}")
        finally:
            self._cleanup()

    def _handle_options(self):
        """Handle OPTIONS request."""
        response = (
            f"RTSP/1.0 200 OK\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
        )
        self.socket.send(response.encode())

    def _handle_describe(self, request_line):
        """Handle DESCRIBE request."""
        # Generate SDP (Session Description Protocol)
        sdp = (
            "v=0\r\n"
            "o=StreamServer 123456 654321 IN IP4 0.0.0.0\r\n"
            "s=H264 Stream\r\n"
            "c=IN IP4 0.0.0.0\r\n"
            "t=0 0\r\n"
            "m=video 0 RTP/AVP 96\r\n"
            "a=rtpmap:96 H264/90000\r\n"
            "a=fmtp:96 profile-level-id=42e01e; sprop-parameter-sets=Z0IAKpY1QPAET8s3AQEBQAAAAAAGkOAAGUAA=,aM4xUg==\r\n"
            "a=control:track1\r\n"
        )
        
        content_length = len(sdp.encode())
        response = (
            f"RTSP/1.0 200 OK\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: {content_length}\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
            f"{sdp}"
        )
        self.socket.send(response.encode())

    def _handle_setup(self, headers):
        """Handle SETUP request."""
        transport = headers.get('transport', '')
        
        # Parse client ports
        client_port_match = None
        if 'client_port=' in transport:
            port_part = transport.split('client_port=')[1].split(';')[0]
            if '-' in port_part:
                rtp_port, rtcp_port = map(int, port_part.split('-'))
            else:
                rtp_port = int(port_part)
                rtcp_port = rtp_port + 1
        else:
            # Default ports
            rtp_port = 5004
            rtcp_port = 5005

        # Create session
        session_id = str(random.randint(100000, 999999))
        self.session = RTSPSession(self.socket, session_id)
        self.session.rtp_port = rtp_port
        self.session.rtcp_port = rtcp_port
        
        # Create RTP socket
        try:
            self.session.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.session.rtcp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            logger.error(f"❌ Failed to create RTP sockets: {e}")
            self._send_response(500, "Internal Server Error")
            return

        response = (
            f"RTSP/1.0 200 OK\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Session: {session_id}\r\n"
            f"Transport: RTP/AVP/UDP;unicast;client_port={rtp_port}-{rtcp_port}\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
        )
        self.socket.send(response.encode())

    def _handle_play(self):
        """Handle PLAY request."""
        if not self.session:
            self._send_response(455, "Method Not Valid in This State")
            return
            
        self.session.is_playing = True
        
        # Add session to stream output
        self.stream_output.add_client(self.session)
        
        response = (
            f"RTSP/1.0 200 OK\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Session: {self.session.session_id}\r\n"
            f"Range: npt=0-\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
        )
        self.socket.send(response.encode())
        logger.info(f"📺 Client {self.client_address} started playing stream")

    def _handle_teardown(self):
        """Handle TEARDOWN request."""
        if self.session:
            self.session.is_playing = False
            self.stream_output.remove_client(self.session)
            
        response = (
            f"RTSP/1.0 200 OK\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
        )
        self.socket.send(response.encode())
        logger.info(f"📺 Client {self.client_address} stopped stream")

    def _send_response(self, code, reason):
        """Send RTSP response."""
        response = (
            f"RTSP/1.0 {code} {reason}\r\n"
            f"CSeq: {self.cseq}\r\n"
            f"Server: StreamServer/1.0\r\n"
            f"\r\n"
        )
        self.socket.send(response.encode())

    def _cleanup(self):
        """Cleanup handler resources."""
        if self.session:
            self.stream_output.remove_client(self.session)
            self.session.close()
        try:
            self.socket.close()
        except:
            pass


class RTSPServer:
    """RTSP server for H.264 streaming."""
    
    def __init__(self, host, port, stream_output):
        """Initialize RTSP server."""
        self.host = host
        self.port = port
        self.stream_output = stream_output
        self.socket = None
        self.is_running = False
        
    def start(self):
        """Start the RTSP server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.is_running = True
            
            logger.info(f"📡 RTSP server started on rtsp://{self.host or 'localhost'}:{self.port}/stream")
            
            while self.is_running:
                try:
                    client_socket, client_address = self.socket.accept()
                    logger.debug(f"📱 RTSP client connected: {client_address}")
                    
                    # Handle client in separate thread
                    handler_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    handler_thread.start()
                    
                except Exception as e:
                    if self.is_running:
                        logger.error(f"❌ Error accepting RTSP connection: {e}")
                        
        except Exception as e:
            logger.error(f"❌ RTSP server error: {e}", exc_info=True)
            raise

    def _handle_client(self, client_socket, client_address):
        """Handle RTSP client connection."""
        handler = RTSPHandler(client_socket, client_address, self.stream_output)
        handler.handle_request()
        
    def stop(self):
        """Stop the RTSP server."""
        self.is_running = False
        if self.socket:
            try:
                self.socket.close()
                logger.info("📡 RTSP server stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping RTSP server: {e}")


def initialize_camera(config):
    """Initialize and configure the camera with H.264 encoding.
    
    Args:
        config: Application configuration
        
    Returns:
        tuple: (Picamera2 instance, H264Encoder instance)
        
    Raises:
        CameraError: If camera initialization fails
    """
    try:
        logger.info("📷 Initializing Picamera2 with H.264 hardware encoding...")
        picam2 = Picamera2()
        
        try:
            # Configure camera for H.264 encoding
            logger.debug(f"📐 Creating video configuration for {config.camera.resolution}")
            
            # Use lower resolution for Pi 3B+ efficiency - can be adjusted in config
            video_config = picam2.create_video_configuration(
                main={"size": config.camera.resolution, "format": "YUV420"}
            )
            
            logger.debug("🔧 Configuring camera with video config")
            picam2.configure(video_config)
            
            # Create H.264 encoder with Pi 3B+ optimized settings
            encoder = H264Encoder(
                bitrate=1000000,  # 1Mbps - good balance for Pi 3B+
                repeat=True,
                iperiod=30  # I-frame every 30 frames (1 second at 30fps)
            )
            
            logger.info(f"✅ Camera initialized: {config.camera.resolution} with H.264 hardware encoding")
            return picam2, encoder
            
        except Exception as config_error:
            logger.error(f"❌ Camera configuration failed: {config_error}", exc_info=True)
            raise CameraError(f"Failed to configure camera: {config_error}")
        
    except Exception as e:
        logger.error(f"❌ Camera initialization failed: {e}", exc_info=True)
        raise CameraError(f"Failed to initialize camera: {e}")


def start_camera_streaming(picam2, encoder, output):
    """Start camera streaming with H.264 encoding.
    
    Args:
        picam2: Camera instance
        encoder: H.264 encoder instance
        output: H264StreamOutput instance
        
    Returns:
        bool: True if camera started successfully
    """
    try:
        if output is None:
            logger.error("❌ Output is None - cannot start camera")
            return False
        
        logger.info("🔧 Starting camera streaming with H.264 encoding")
        try:
            # Set up encoder output to our stream
            encoder.output = FileOutput(output)
            
            # Start recording with H.264 encoder
            picam2.start_recording(encoder)
            logger.info("✅ Camera started with hardware H.264 encoding")
            return True
            
        except Exception as start_error:
            logger.error(f"❌ Failed to start camera recording: {start_error}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to start camera streaming: {e}", exc_info=True)
        return False


def stop_camera_streaming(picam2):
    """Stop camera streaming.
    
    Args:
        picam2: Camera instance
    """
    try:
        if picam2:
            logger.debug("🛑 Stopping camera recording...")
            picam2.stop_recording()
            logger.debug("📹 Camera recording stopped")
    except Exception as e:
        logger.warning(f"⚠️ Error stopping camera recording: {e}")


def run_stream_server():
    """Main server loop for RTSP streaming."""
    
    config = AppConfig()
    restart_count = 0
    max_restarts = 10
    restart_requested = Event()
    restart_reason = None
    
    def request_restart(reason):
        """Callback function to request a restart."""
        nonlocal restart_reason
        restart_reason = reason
        restart_requested.set()
    
    while True:
        picam2 = None
        encoder = None
        server_instance = None
        stream_monitor = None
        restart_requested.clear()
        
        try:
            restart_count += 1
            logger.info(f"🚀 Starting RTSP stream server (attempt #{restart_count})")
            
            # Initialize camera with retry logic
            camera_retry_count = 0
            max_camera_retries = 3
            
            while camera_retry_count < max_camera_retries:
                try:
                    camera_retry_count += 1
                    logger.debug(f"🔄 Camera initialization attempt {camera_retry_count}/{max_camera_retries}")
                    picam2, encoder = initialize_camera(config)
                    logger.debug("✅ Camera initialization completed")
                    break
                except Exception as camera_init_error:
                    logger.error(f"❌ Camera initialization failed (attempt {camera_retry_count}/{max_camera_retries}): {camera_init_error}", exc_info=True)
                    if camera_retry_count >= max_camera_retries:
                        raise CameraError(f"Camera initialization failed after {max_camera_retries} attempts")
                    logger.info(f"⏳ Retrying camera initialization in 3 seconds...")
                    time.sleep(3)
            
            try:
                # Initialize H.264 streaming output
                output = H264StreamOutput()
                logger.info("🔧 Created H.264 streaming output")
                
                # Initialize stream monitor
                stream_monitor = StreamMonitor(output, request_restart, check_interval=5.0, max_frame_age=10.0)
                
                logger.info("📊 Configuration:")
                logger.info(f"   - Camera resolution: {config.camera.resolution}")
                logger.info(f"   - RTSP port: {config.server.port}")
                logger.info(f"   - H.264 bitrate: 1Mbps (optimized for Pi 3B+)")
                
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
                    if not start_camera_streaming(picam2, encoder, output):
                        raise CameraError("Failed to start streaming")
                    logger.debug("✅ Camera streaming started successfully")
                    break
                except Exception as streaming_error:
                    logger.error(f"❌ Camera streaming failed (attempt {streaming_retry_count}/{max_streaming_retries}): {streaming_error}", exc_info=True)
                    if streaming_retry_count >= max_streaming_retries:
                        raise CameraError(f"Camera streaming failed after {max_streaming_retries} attempts")
                    logger.info(f"⏳ Retrying camera streaming in 2 seconds...")
                    time.sleep(2)
                
            # Start RTSP server
            try:
                logger.debug(f"📡 Creating RTSP server on {config.server.host}:{config.server.port}")
                server_instance = RTSPServer(config.server.host, config.server.port, output)
                
                logger.info(f"📡 RTSP stream server started on rtsp://localhost:{config.server.port}/stream")
                logger.info("📹 Hardware H.264 stream available for VLC, FFmpeg, etc.")
                logger.info("🎯 Optimized for Pi 3B+ with up to 4 concurrent clients")
                
                # Start stream monitoring
                stream_monitor.start_monitoring()
                
                try:
                    logger.debug("🔄 Starting RTSP server...")
                    
                    # Run server in a separate thread so we can monitor for restart requests
                    server_thread = threading.Thread(target=server_instance.start, daemon=True)
                    server_thread.start()
                    
                    # Wait for either the server to stop or a restart request
                    while server_thread.is_alive():
                        if restart_requested.wait(timeout=1.0):  # Check every second
                            logger.warning(f"🔄 Restart requested: {restart_reason}")
                            break
                            
                    if restart_requested.is_set():
                        # Restart was requested by monitor
                        raise CameraError(f"Stream restart requested: {restart_reason}")
                    
                except Exception as serve_error:
                    logger.error(f"❌ Server serving error: {serve_error}", exc_info=True)
                    # Don't raise here - let the outer exception handler restart everything
                    
                finally:
                    logger.info("🛑 Shutting down RTSP server...")
                    try:
                        if server_instance:
                            server_instance.stop()
                            logger.debug("✅ RTSP server shutdown completed")
                    except Exception as shutdown_error:
                        logger.error(f"❌ RTSP server shutdown error: {shutdown_error}", exc_info=True)
                        
            except Exception as server_error:
                logger.error(f"❌ RTSP server creation/start failed: {server_error}", exc_info=True)
                raise CameraError(f"RTSP server failed: {server_error}")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal")
            break
        except CameraError as camera_error:
            logger.error(f"🔄 Camera error - restarting: {camera_error}", exc_info=True)
            if restart_count >= max_restarts:
                logger.critical(f"🚨 Too many camera restart attempts ({restart_count}/{max_restarts}) - exiting")
                break
            
            # Add delay based on error type
            if "Stream restart requested" in str(camera_error):
                logger.info(f"🔄 Stream monitor triggered restart - restarting immediately (attempt {restart_count + 1})")
                time.sleep(1)  # Brief pause for cleanup
            else:
                logger.info(f"🔄 Restarting camera and server in 5 seconds... (attempt {restart_count + 1})")
                time.sleep(5)
        except Exception as e:
            logger.error(f"💥 Unexpected server error - restarting: {e}", exc_info=True)
            if restart_count >= max_restarts:
                logger.critical(f"🚨 Too many restart attempts ({restart_count}/{max_restarts}) - exiting")
                break
            logger.info(f"🔄 Restarting in 5 seconds... (attempt {restart_count + 1})")
            time.sleep(5)
        finally:
            # Always cleanup camera, server, and monitor resources
            if stream_monitor:
                try:
                    stream_monitor.stop_monitoring()
                    logger.debug("🛑 Stream monitor stopped")
                except Exception as monitor_error:
                    logger.error(f"❌ Error stopping stream monitor: {monitor_error}", exc_info=True)
                    
            if picam2:
                try:
                    logger.debug("🔄 Stopping camera...")
                    stop_camera_streaming(picam2)
                    picam2.close()
                    logger.info("📹 Camera closed")
                except Exception as camera_close_error:
                    logger.error(f"❌ Error closing camera: {camera_close_error}", exc_info=True)
                    
            if server_instance:
                try:
                    server_instance.stop()
                    logger.debug("📡 RTSP server closed")
                except Exception as socket_close_error:
                    logger.error(f"❌ Error closing RTSP server: {socket_close_error}", exc_info=True)


def main():
    """Main entry point."""
    try:
        logger.info("🎬 RTSP Stream Server Starting...")
        run_stream_server()
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        raise
    except KeyboardInterrupt:
        logger.info("👋 Interrupted by user")
    finally:
        logger.info("👋 RTSP Stream Server stopped")


if __name__ == "__main__":
    main()