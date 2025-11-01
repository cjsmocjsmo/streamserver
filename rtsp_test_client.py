#!/usr/bin/env python3
"""
Simple RTSP client to test the server functionality.
This helps diagnose RTSP issues without relying on VLC.
"""

import socket
import time

def test_rtsp_full_session():
    """Test a complete RTSP session."""
    server_ip = "10.0.4.67"  # Change this to your Pi's IP
    server_port = 8554
    
    try:
        print(f"🔌 Connecting to RTSP server at {server_ip}:{server_port}")
        
        # Connect to RTSP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect((server_ip, server_port))
        print("✅ Connected to RTSP server")
        
        # 1. OPTIONS request
        print("\n📡 Sending OPTIONS request...")
        options_request = (
            f"OPTIONS rtsp://{server_ip}:{server_port}/stream RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"User-Agent: TestClient/1.0\r\n"
            f"\r\n"
        )
        sock.send(options_request.encode())
        response = sock.recv(1024).decode()
        print(f"📨 OPTIONS Response:\n{response}")
        
        # 2. DESCRIBE request
        print("\n📡 Sending DESCRIBE request...")
        describe_request = (
            f"DESCRIBE rtsp://{server_ip}:{server_port}/stream RTSP/1.0\r\n"
            f"CSeq: 2\r\n"
            f"Accept: application/sdp\r\n"
            f"User-Agent: TestClient/1.0\r\n"
            f"\r\n"
        )
        sock.send(describe_request.encode())
        response = sock.recv(2048).decode()
        print(f"📨 DESCRIBE Response:\n{response}")
        
        # 3. SETUP request
        print("\n📡 Sending SETUP request...")
        setup_request = (
            f"SETUP rtsp://{server_ip}:{server_port}/stream/track1 RTSP/1.0\r\n"
            f"CSeq: 3\r\n"
            f"Transport: RTP/AVP/UDP;unicast;client_port=5004-5005\r\n"
            f"User-Agent: TestClient/1.0\r\n"
            f"\r\n"
        )
        sock.send(setup_request.encode())
        response = sock.recv(1024).decode()
        print(f"📨 SETUP Response:\n{response}")
        
        # Extract session ID
        session_id = None
        for line in response.split('\r\n'):
            if line.startswith('Session:'):
                session_id = line.split(':')[1].strip()
                break
        
        if not session_id:
            print("❌ No session ID received!")
            return
            
        print(f"📋 Session ID: {session_id}")
        
        # 4. PLAY request
        print("\n📡 Sending PLAY request...")
        play_request = (
            f"PLAY rtsp://{server_ip}:{server_port}/stream RTSP/1.0\r\n"
            f"CSeq: 4\r\n"
            f"Session: {session_id}\r\n"
            f"Range: npt=0-\r\n"
            f"User-Agent: TestClient/1.0\r\n"
            f"\r\n"
        )
        sock.send(play_request.encode())
        response = sock.recv(1024).decode()
        print(f"📨 PLAY Response:\n{response}")
        
        if "200 OK" in response:
            print("✅ PLAY successful - stream should be active")
            
            # Set up UDP socket to listen for RTP
            print("\n📡 Setting up RTP listener on port 5004...")
            rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rtp_sock.settimeout(5.0)
            rtp_sock.bind(('', 5004))
            
            print("📡 Listening for RTP packets...")
            packet_count = 0
            start_time = time.time()
            
            try:
                while packet_count < 10 and time.time() - start_time < 30:
                    data, addr = rtp_sock.recvfrom(2048)
                    packet_count += 1
                    print(f"📦 RTP packet {packet_count}: {len(data)} bytes from {addr}")
                    
                    # Parse RTP header
                    if len(data) >= 12:
                        version = (data[0] >> 6) & 0x3
                        payload_type = data[1] & 0x7f
                        seq_num = int.from_bytes(data[2:4], 'big')
                        timestamp = int.from_bytes(data[4:8], 'big')
                        print(f"   📋 RTP: v={version}, pt={payload_type}, seq={seq_num}, ts={timestamp}")
                        
            except socket.timeout:
                print("⏰ Timeout waiting for RTP packets")
            
            rtp_sock.close()
            
            if packet_count > 0:
                print(f"✅ Received {packet_count} RTP packets - stream is working!")
            else:
                print("❌ No RTP packets received - there's an issue with the stream")
        else:
            print("❌ PLAY request failed")
            
        # 5. TEARDOWN
        print("\n📡 Sending TEARDOWN request...")
        teardown_request = (
            f"TEARDOWN rtsp://{server_ip}:{server_port}/stream RTSP/1.0\r\n"
            f"CSeq: 5\r\n"
            f"Session: {session_id}\r\n"
            f"User-Agent: TestClient/1.0\r\n"
            f"\r\n"
        )
        sock.send(teardown_request.encode())
        response = sock.recv(1024).decode()
        print(f"📨 TEARDOWN Response:\n{response}")
        
        sock.close()
        print("🔌 Connection closed")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 RTSP Full Session Test")
    print("=" * 50)
    test_rtsp_full_session()