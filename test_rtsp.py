#!/usr/bin/env python3
"""
Test script for RTSP server functionality.
This script can be used to verify the RTSP server without requiring a camera.
"""

import socket
import time
import logging
import sys


def setup_simple_logging():
    """Set up simple logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def test_rtsp_connection():
    """Test basic RTSP connection and protocol."""
    try:
        # Connect to RTSP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        
        logging.info("🔌 Connecting to RTSP server...")
        sock.connect(('localhost', 554))
        logging.info("✅ Connected to RTSP server")
        
        # Send OPTIONS request
        options_request = (
            "OPTIONS rtsp://localhost:554/stream RTSP/1.0\r\n"
            "CSeq: 1\r\n"
            "User-Agent: TestClient/1.0\r\n"
            "\r\n"
        )
        
        logging.info("📡 Sending OPTIONS request...")
        sock.send(options_request.encode())
        
        # Receive response
        response = sock.recv(1024).decode()
        logging.info(f"📨 Received response:\n{response}")
        
        if "200 OK" in response:
            logging.info("✅ RTSP OPTIONS successful")
        else:
            logging.warning("⚠️ Unexpected RTSP response")
            
        sock.close()
        logging.info("🔌 Connection closed")
        
    except ConnectionRefusedError:
        logging.error("❌ RTSP server not running or not accessible")
    except socket.timeout:
        logging.error("❌ Connection timeout - server may be busy")
    except Exception as e:
        logging.error(f"❌ RTSP test error: {e}")


def test_rtsp_describe():
    """Test RTSP DESCRIBE request."""
    try:
        # Connect to RTSP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        
        logging.info("🔌 Connecting for DESCRIBE test...")
        sock.connect(('localhost', 554))
        
        # Send DESCRIBE request
        describe_request = (
            "DESCRIBE rtsp://localhost:554/stream RTSP/1.0\r\n"
            "CSeq: 2\r\n"
            "Accept: application/sdp\r\n"
            "User-Agent: TestClient/1.0\r\n"
            "\r\n"
        )
        
        logging.info("📡 Sending DESCRIBE request...")
        sock.send(describe_request.encode())
        
        # Receive response
        response = sock.recv(2048).decode()
        logging.info(f"📨 DESCRIBE response:\n{response}")
        
        if "application/sdp" in response and "H264" in response:
            logging.info("✅ RTSP DESCRIBE successful with H.264 SDP")
        else:
            logging.warning("⚠️ Unexpected DESCRIBE response")
            
        sock.close()
        
    except Exception as e:
        logging.error(f"❌ RTSP DESCRIBE test error: {e}")


def main():
    """Run RTSP tests."""
    setup_simple_logging()
    logging.info("🧪 Starting RTSP server tests...")
    
    # Wait a moment for server to start if just launched
    logging.info("⏳ Waiting 2 seconds for server startup...")
    time.sleep(2)
    
    # Test basic connection
    test_rtsp_connection()
    time.sleep(1)
    
    # Test DESCRIBE
    test_rtsp_describe()
    
    logging.info("🧪 RTSP tests completed")


if __name__ == "__main__":
    main()