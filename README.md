# Motion Detection Stream Server v2.0

A professional-grade video streaming server with real-time motion detection capabilities for Raspberry Pi.

## 🌟 Features

- **Real-time MJPEG Streaming**: High-performance video streaming with web interface
- **OpenCV Motion Detection**: Advanced background subtraction with configurable sensitivity
- **Automatic Recording**: Pre/post motion buffers with configurable durations
- **SQLite Event Logging**: Complete database tracking of all motion events
- **Multi-threaded Architecture**: Optimized for smooth performance
- **Web Monitoring Interface**: Beautiful, responsive web UI
- **Error Recovery**: Automatic stream health monitoring and recovery
- **Modular Design**: Clean, maintainable Python code following best practices

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi with camera module
- Raspberry Pi OS (recommended)

### Installation

**Important**: This project uses APT packages only to comply with PEP 668 (externally-managed-environment) on modern Debian/Ubuntu systems.

1. **Automated setup (recommended):**
   ```bash
   git clone <your-repo>
   cd streamserver
   python3 setup.py
   ```
   
   The setup script will automatically:
   - Install all required packages via `apt` (python3-opencv, python3-numpy, python3-picamera2)
   - Create necessary directories
   - Provide clear error messages if packages cannot be installed

2. **Manual installation (if needed):**
   ```bash
   # Install all dependencies via apt
   sudo apt update
   sudo apt install python3-opencv python3-numpy python3-picamera2
   ```

**Note**: This project deliberately avoids pip installation to comply with PEP 668 externally-managed-environment restrictions on modern systems. All required packages are available in Debian/Ubuntu repositories.

3. **Run the server:**
   ```bash
   python3 streamserver.py
   ```

4. **Access the web interface:**
   Open http://localhost:8000 in your browser

## 📁 Project Structure

```
streamserver/
├── streamserver.py         # Main application
├── config.py              # Configuration management
├── database.py            # SQLite event database
├── motion_detector.py     # OpenCV motion detection
├── video_recorder.py      # Video recording and buffering
├── dependencies.py        # Dependency management
├── exceptions.py          # Custom exception classes
├── logger.py             # Logging configuration
├── setup.py              # Setup script
├── requirements.txt       # Python dependencies
├── __init__.py           # Package initialization
└── README.md             # This file
```

## ⚙️ Configuration

The application uses a configuration system with sensible defaults. Key settings:

### Motion Detection
- **Threshold**: Motion sensitivity (default: 25)
- **Min Area**: Minimum pixel area for motion (default: 1000)
- **Learning Rate**: Background adaptation rate (default: 0.001)

### Video Recording
- **FPS**: Recording frame rate (default: 30)
- **Pre-buffer**: Seconds to record before motion (default: 5)
- **Post-buffer**: Seconds to record after motion (default: 5)
- **Output Directory**: Where videos are saved (default: "recordings")

### Camera
- **Resolution**: Video resolution (default: 640x480)
- **Format**: Pixel format (default: "RGB888")

## 🗄️ Database Schema

Events are stored in SQLite with the following schema:

```sql
CREATE TABLE Events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Epoch INTEGER NOT NULL,        -- Unix timestamp
    Month INTEGER NOT NULL,        -- 1-12
    Day INTEGER NOT NULL,          -- 1-31
    Year INTEGER NOT NULL,         -- Full year
    Size INTEGER NOT NULL,         -- File size in bytes
    Path TEXT NOT NULL,           -- Full file path
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 API Usage

### Basic Usage
```python
from config import AppConfig
from database import EventDatabase
from motion_detector import MotionDetector
from video_recorder import VideoRecorder, CircularVideoBuffer

# Initialize with default config
config = AppConfig()

# Create components
database = EventDatabase(config.database)
motion_detector = MotionDetector(config.motion)
buffer = CircularVideoBuffer(config.video)
recorder = VideoRecorder(config.video, database)
```

### Custom Configuration
```python
from config import AppConfig, MotionConfig, VideoConfig

config = AppConfig()
config.motion.threshold = 30
config.motion.min_area = 500
config.video.fps = 60
config.video.pre_buffer_duration = 10
```

## 📊 Performance Optimizations

### v2.0 Improvements:
1. **Modular Architecture**: Separated concerns into focused modules
2. **Type Hints**: Full type annotation for better IDE support and debugging
3. **Error Handling**: Comprehensive exception handling with custom exceptions
4. **Logging**: Professional logging system with file and console output
5. **Configuration Management**: Centralized, type-safe configuration system
6. **Database Improvements**: Enhanced schema with better indexing
7. **Thread Safety**: Improved multi-threading with proper synchronization
8. **Resource Management**: Proper cleanup and resource management
9. **Documentation**: Comprehensive docstrings and type hints
10. **Testing Ready**: Structure prepared for unit testing

## 🧪 Testing

The modular structure makes testing easy:

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests (when test files are added)
pytest tests/ -v --cov=.
```

## 📝 Logging

Logs are written to both console and files in the `logs/` directory:
- **Console**: Real-time status and errors
- **Files**: Complete log history with timestamps
- **Levels**: INFO, WARNING, ERROR, CRITICAL

## 🔒 Security Considerations

- **Network Access**: Server binds to all interfaces (0.0.0.0) by default
- **File Permissions**: Ensure proper permissions on recordings directory
- **Resource Limits**: Monitor disk space for recordings and logs

## 🐛 Troubleshooting

### Common Issues:

1. **Camera not found**
   ```
   Solution: Check camera connection and enable camera in raspi-config
   ```

2. **Permission denied**
   ```
   Solution: Ensure user is in 'video' group: sudo usermod -a -G video $USER
   ```

3. **High CPU usage**
   ```
   Solution: Reduce resolution or FPS in configuration
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the existing code style
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- OpenCV community for computer vision tools
- Raspberry Pi Foundation for the excellent camera integration
- Python community for the robust ecosystem