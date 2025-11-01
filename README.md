# RTSP Stream Server

A hardware-accelerated RTSP streaming server for Raspberry Pi camera using Picamera2 with H.264 hardware encoding. Optimized for Raspberry Pi 3B+ with support for 2-4 concurrent clients.

## Features

- **Hardware H.264 Encoding**: Uses Raspberry Pi's GPU for efficient video encoding
- **RTSP Protocol**: Standard streaming protocol compatible with VLC, FFmpeg, and other media players
- **Low Bandwidth**: 10-20x more efficient than MJPEG streaming
- **Multiple Clients**: Supports up to 4 concurrent clients on Pi 3B+
- **Stream Monitoring**: Automatic health checks and restart on failures
- **Optimized for Pi 3B+**: Configured for best performance on older hardware

## Hardware Requirements

- Raspberry Pi 3B+ or newer
- Pi Camera (v1, v2, or HQ camera)
- Sufficient power supply (recommended 2.5A+)

## Configuration

The server is configured in `config.py`:

- **Resolution**: 1280x720 (720p) - optimized for Pi 3B+
- **Bitrate**: 1Mbps - good balance of quality and bandwidth
- **Port**: 8554 (non-privileged port, use 554 for standard RTSP if running as root)
- **Format**: YUV420 (required for H.264)

## Usage

### Direct Execution
```bash
python3 streamserver.py
```

### As System Service
```bash
# Install service
sudo cp streamserver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamserver
sudo systemctl start streamserver

# Check status
sudo systemctl status streamserver

# View logs
sudo journalctl -u streamserver -f
```

### Accessing the Stream

The RTSP stream is available at:
```
rtsp://[PI_IP_ADDRESS]:8554/stream
```

**VLC Media Player:**
1. Open VLC
2. Go to Media → Open Network Stream
3. Enter: `rtsp://192.168.1.100:8554/stream` (replace with your Pi's IP)
4. Click Play

**FFmpeg (for recording or re-streaming):**
```bash
# View stream
ffplay rtsp://192.168.1.100:8554/stream

# Record to file
ffmpeg -i rtsp://192.168.1.100:8554/stream -c copy output.mp4

# Re-stream to YouTube Live
ffmpeg -i rtsp://192.168.1.100:8554/stream -c copy -f flv rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY
```

**OBS Studio:**
1. Add Source → Media Source
2. Input: `rtsp://192.168.1.100:8554/stream`
3. Uncheck "Local File"

## Performance Optimization

### For Pi 3B+:
- Resolution: 720p@15-20fps or 1080p@10-15fps max
- Bitrate: 500kbps-2Mbps range
- Concurrent clients: 2-4 maximum

### Port Configuration:
- **Port 8554**: Default non-privileged port (recommended)
- **Port 554**: Standard RTSP port (requires root privileges)

To use standard port 554, update `config.py`:
```python
@dataclass
class ServerConfig:
    host = ""
    port = 554  # Standard RTSP port (requires root)
```

**Note**: Port 8554 is used by default to avoid permission issues. Most RTSP clients work perfectly with non-standard ports.

## Troubleshooting

### Connection Issues:
1. Check firewall: `sudo ufw allow 8554`
2. Verify Pi's IP address: `ip addr show`
3. Test locally: `python3 test_rtsp.py`

### Performance Issues:
1. Reduce resolution in `config.py`
2. Lower bitrate in camera initialization
3. Limit concurrent clients
4. Check CPU usage: `htop`

### Camera Issues:
1. Enable camera: `sudo raspi-config` → Interface Options → Camera
2. Check camera connection: `libcamera-hello --timeout 5000`
3. Verify permissions: user must be in `video` group

### Stream Quality:
- **Pixelated**: Increase bitrate (but watch bandwidth)
- **Laggy**: Reduce resolution or framerate
- **Stuttering**: Check network stability

## Logs and Monitoring

Logs are written to:
- `/tmp/streamserver.log` - General application logs
- `/tmp/streamserver_errors.log` - Error-specific logs

View real-time logs:
```bash
tail -f /tmp/streamserver.log
```

## Technical Details

### H.264 Encoding:
- Uses VideoCore IV hardware encoder
- NAL unit parsing for proper RTP packetization
- SPS/PPS parameter sets for decoder initialization

### RTSP Implementation:
- Standards-compliant RTSP 1.0 protocol
- RTP/UDP transport for media data
- Session management for multiple clients

### Bandwidth Usage:
- **MJPEG (old)**: ~5-15 Mbps for 720p
- **H.264 (new)**: ~1-2 Mbps for 720p
- **Savings**: 80-90% bandwidth reduction

## Comparison with Previous MJPEG Version

| Feature | MJPEG (Old) | H.264 RTSP (New) |
|---------|-------------|------------------|
| Bandwidth | 5-15 Mbps | 1-2 Mbps |
| CPU Usage | Medium | Low (GPU encoding) |
| Compatibility | Web browsers | Media players |
| Latency | Low | Very low |
| Quality | Good | Excellent |
| Clients | 2-3 max | 4+ supported |

The new RTSP implementation is significantly more efficient and suitable for the Pi 3B+ hardware limitations.