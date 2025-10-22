# 🎥 Motion Detection Stream Server

A Raspberry Pi streaming server with intelligent motion detection and automatic video recording capabilities.

## ✨ Features

### Core Streaming
- **Real-time MJPEG streaming** at 640x480 resolution
- **Web interface** accessible at `http://localhost:8000`
- **Robust error handling** with automatic recovery
- **Systemd service** for automatic startup

### Motion Detection
- **Advanced motion detection** using OpenCV background subtraction
- **Configurable sensitivity** settings
- **Smart noise filtering** to reduce false positives
- **Real-time processing** with optimized CPU usage

### Video Recording
- **Automatic recording** when motion is detected
- **5-second pre-buffer** captures events before detection
- **Continuous recording** until motion stops
- **5-second post-motion** recording for complete coverage
- **MP4 format** with H.264 encoding
- **Timestamped filenames** for easy organization

## 🚀 Quick Start

### 1. Install Dependencies
```bash
./install-opencv.sh
```

### 2. Run the Server
```bash
source venv/bin/activate
python3 streamserver.py
```

### 3. Access the Stream
Open your browser to `http://localhost:8000`

## ⚙️ Configuration

Edit `motion_config.ini` to customize motion detection:

```ini
[motion_detection]
threshold = 25          # Lower = more sensitive
min_area = 500         # Minimum pixels to trigger
blur_size = 21         # Noise reduction

[recording]
prebuffer_duration = 5  # Seconds to record before motion
post_motion_timeout = 5 # Seconds to record after motion stops
fps = 30               # Recording frame rate
output_directory = recordings
```

## 📁 File Structure

```
streamserver/
├── streamserver.py           # Main server with motion detection
├── motion_config.ini         # Configuration settings
├── requirements.txt          # Python dependencies
├── install-opencv.sh         # Setup script
├── streamserver.service      # Systemd service file
├── install-service.sh        # Service installer
├── uninstall-service.sh      # Service remover
└── recordings/               # Auto-created video directory
```

## 🔧 Systemd Service

### Install as System Service
```bash
./install-service.sh
```

### Service Commands
```bash
# Start/stop/restart
sudo systemctl start streamserver
sudo systemctl stop streamserver
sudo systemctl restart streamserver

# Check status
sudo systemctl status streamserver

# View logs
sudo journalctl -u streamserver -f
```

## 📊 Motion Detection Details

### Algorithm
- **Background Subtraction**: MOG2 algorithm learns background patterns
- **Noise Filtering**: Morphological operations remove sensor noise
- **Contour Analysis**: Only significant movement areas trigger recording
- **Smart Buffering**: Circular buffer maintains 5 seconds of recent frames

### Performance
- **CPU Optimized**: Processes every 3rd frame to reduce load
- **Memory Efficient**: Circular buffer prevents memory leaks
- **Adaptive**: Background model adapts to lighting changes

### Recording Logic
1. **Continuous buffering** of last 5 seconds
2. **Motion detected** → Start recording with pre-buffer
3. **Motion continues** → Keep recording
4. **Motion stops** → Continue for 5 more seconds
5. **Save video** → Timestamped MP4 file

## 🎛️ Tuning Motion Detection

### Too Sensitive (False Positives)
- Increase `threshold` (try 35-50)
- Increase `min_area` (try 800-1500)
- Adjust camera placement to avoid trees/shadows

### Not Sensitive Enough (Missing Motion)
- Decrease `threshold` (try 15-20)
- Decrease `min_area` (try 200-400)
- Ensure adequate lighting

### CPU Usage Too High
- Increase `frame_skip` to process fewer frames
- Reduce recording fps
- Lower camera resolution

## 📹 Video Output

### File Format
- **Container**: MP4
- **Video Codec**: H.264 (mp4v)
- **Resolution**: 640x480
- **Frame Rate**: 30 FPS
- **Naming**: `motion_YYYYMMDD_HHMMSS.mp4`

### Storage Management
Videos are saved to the `recordings/` directory. Consider setting up:
- **Automatic cleanup** of old recordings
- **External storage** for large volumes
- **Cloud backup** for important recordings

## 🛠️ Troubleshooting

### Common Issues

**Camera not found:**
```bash
# Check camera connection
vcgencmd get_camera

# Ensure user in video group
sudo usermod -a -G video $USER
```

**OpenCV installation failed:**
```bash
# Install system dependencies
sudo apt install python3-opencv libopencv-dev

# Use system OpenCV
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
```

**High CPU usage:**
- Increase `frame_skip` in motion detection
- Reduce camera resolution
- Adjust motion detection frequency

**False motion detection:**
- Increase motion threshold
- Increase minimum area
- Check for camera vibration
- Avoid auto-focus cameras

### Logs
Monitor system logs for debugging:
```bash
# Application logs
sudo journalctl -u streamserver -f

# System logs
tail -f /var/log/syslog | grep streamserver
```

## 🔒 Security Considerations

- Server runs on port 8000 (not secured)
- Consider adding authentication for public access
- Recordings contain sensitive video data
- Ensure proper file permissions on recording directory

## 📝 License

This project is open source. Feel free to modify and distribute.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Happy Motion Detecting! 🎯**