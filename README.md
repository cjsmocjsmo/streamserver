# Simple MJPEG Stream Server

A minimal, high-performance video streaming server for Raspberry Pi camera with automatic error recovery.

## 🌟 Features

- **Real-time MJPEG Streaming**: High-performance video streaming via HTTP
- **Minimal Dependencies**: Only Picamera2 and OpenCV for JPEG encoding
- **Automatic Error Recovery**: Camera restart on any errors with comprehensive logging
- **Multi-threaded Architecture**: Optimized for smooth streaming performance
- **Comprehensive Logging**: Detailed error logging with separate error files
- **Service Integration**: Systemd service files for automatic startup

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi with camera module
- Raspberry Pi OS (recommended)

### Installation

```bash
# Install system dependencies
sudo apt update
sudo apt install python3-opencv python3-picamera2

# Clone and run
git clone <your-repo>
cd streamserver
python3 streamserver.py
```

### Access the Stream

Open http://localhost:8000/stream.mjpg in your browser or media player

## 📁 Project Structure

```
streamserver/
├── streamserver.py         # Main streaming server
├── config.py              # Camera and server configuration
├── dependencies.py        # Dependency verification
├── exceptions.py          # Custom exception classes  
├── logger.py             # Comprehensive logging system
├── streamserver.service   # Systemd service file
├── install-service.sh     # Service installer script
├── uninstall-service.sh   # Service uninstaller script
└── README.md             # This file
```

## ⚙️ Configuration

The server uses minimal configuration with sensible defaults:

### Camera Settings
- **Resolution**: 640x480 (configurable in config.py)
- **Format**: RGB888 for compatibility
- **FPS**: 30 fps for smooth streaming

### Server Settings  
- **Host**: All interfaces (0.0.0.0)
- **Port**: 8000 (configurable in config.py)

## 🔄 Error Recovery

The server includes comprehensive error recovery:

- **Camera Restart**: Automatic camera restart on any hardware errors
- **Retry Logic**: Multiple retry attempts for camera initialization and streaming
- **Error Logging**: Detailed error logs with full stack traces
- **Graceful Degradation**: Clean shutdown after maximum restart attempts

## 🗂️ Logging

Comprehensive logging system:
- **Main Log**: All operations and debug information
- **Error Log**: Dedicated error file for troubleshooting
- **Console Output**: Real-time status and important messages
- **Exception Capture**: Automatic capture of uncaught exceptions

Log files are created in the `logs/` directory with timestamps.

## 🔧 Installation as Service

Install as a systemd service for automatic startup:

```bash
# Install service
./install-service.sh

# Control service
sudo systemctl start streamserver
sudo systemctl stop streamserver  
sudo systemctl status streamserver

# View logs
sudo journalctl -u streamserver -f
```

## 📊 Performance

Optimized for minimal resource usage:
- **Low CPU**: Efficient JPEG encoding and streaming
- **Low Memory**: Minimal buffering with circular frame buffer
- **Automatic Recovery**: Restart on errors to maintain uptime
- **Thread Safety**: Proper synchronization for multi-threaded operation

## 🔒 Security Considerations

- **Network Access**: Server binds to all interfaces by default
- **Camera Permissions**: Ensure user is in 'video' group
- **Resource Limits**: Monitor system resources during operation

## 🐛 Troubleshooting

### Common Issues:

1. **Camera not found**
   ```
   Solution: Check camera connection and enable camera interface
   ```

2. **Permission denied**
   ```
   Solution: Add user to video group: sudo usermod -a -G video $USER
   ```

3. **Import errors**
   ```
   Solution: Install packages: sudo apt install python3-opencv python3-picamera2
   ```

4. **Stream not accessible**
   ```
   Solution: Check firewall and network configuration
   ```

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Raspberry Pi Foundation for excellent camera integration
- OpenCV community for image processing tools
- Python community for the robust ecosystem