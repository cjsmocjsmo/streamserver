# 🍓 Raspberry Pi 3B+ Motion Detection Docker Guide

A containerized motion detection stream server specifically optimized for Raspberry Pi 3B+ with Debian package priority.

## 🚀 Quick Start

### 1. Prerequisites
```bash
# Install Docker (if not already installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install docker-compose
sudo apt-get update
sudo apt-get install -y docker-compose

# Log out and log back in for group changes
```

### 2. Build and Run
```bash
# Make script executable
chmod +x docker-pi3b.sh

# Quick start (builds and runs everything)
./docker-pi3b.sh run
```

### 3. Access the Stream
- **Web Interface**: http://localhost:8000
- **Recordings**: `./recordings/` directory
- **Logs**: `./logs/` directory

## 🔧 Management Commands

```bash
# Show service status
./docker-pi3b.sh status

# View real-time logs
./docker-pi3b.sh logs

# Stop the service
./docker-pi3b.sh stop

# Restart the service
./docker-pi3b.sh restart

# Update and rebuild
./docker-pi3b.sh update

# Show system info
./docker-pi3b.sh info

# Complete cleanup
./docker-pi3b.sh cleanup
```

## 🎛️ Configuration

Edit `motion_config.ini` to adjust motion detection settings:
```ini
[motion_detection]
threshold = 25          # Motion sensitivity
min_area = 500         # Minimum motion area
prebuffer_duration = 10 # Pre-record seconds
```

Changes take effect after restart:
```bash
./docker-pi3b.sh restart
```

## 🏗️ Container Features

### Pi 3B+ Optimizations
- **ARM-optimized packages**: Uses Debian system packages
- **GPU acceleration**: Enabled for camera processing
- **Memory limits**: Configured for 1GB RAM
- **Hardware access**: Camera, GPU, GPIO support

### Security
- **Non-root user**: Runs as dedicated `streamuser`
- **Minimal privileges**: Only required hardware access
- **Read-only mounts**: Configuration and system files

### Monitoring
- **Health checks**: Automatic container health monitoring
- **Resource limits**: Prevents memory exhaustion
- **Automatic restart**: Service recovers from failures

## 📊 Monitoring

### Check Resource Usage
```bash
# Container stats
docker stats motion-detection-pi3b

# System resources
./docker-pi3b.sh info
```

### View Logs
```bash
# Real-time application logs
./docker-pi3b.sh logs

# System logs
sudo journalctl -u docker -f
```

## 🔧 Troubleshooting

### Camera Not Detected
```bash
# Check camera device
ls -la /dev/video*

# Test camera
raspistill -o test.jpg

# Verify user permissions
groups $USER | grep video
```

### Container Won't Start
```bash
# Check container logs
docker logs motion-detection-pi3b

# Verify Docker daemon
sudo systemctl status docker

# Check system resources
free -h && df -h
```

### Performance Issues
```bash
# Monitor container resources
docker stats --no-stream

# Check GPU memory split
vcgencmd get_mem gpu

# Adjust motion detection settings
# Edit motion_config.ini: increase frame_skip, threshold
```

## 📁 File Structure

```
streamserver/
├── Dockerfile              # Pi 3B+ optimized container
├── docker-compose.yml      # Service configuration
├── docker-pi3b.sh         # Management script
├── .dockerignore           # Build exclusions
├── streamserver.py         # Motion detection server
├── motion_config.ini       # Configuration file
├── DOCKER_DEPS.md         # Dependency documentation
├── recordings/             # Video storage (created)
└── logs/                   # Application logs (created)
```

## 🔒 Security Notes

- Container runs with minimal required privileges
- Camera and GPU access only as needed
- Configuration mounted read-only
- No unnecessary network exposure

## 📈 Performance Tuning

### For Better Performance
```ini
# In motion_config.ini
frame_skip = 5           # Process fewer frames
threshold = 35           # Less sensitive detection
```

### For Better Detection
```ini
# In motion_config.ini
frame_skip = 2           # Process more frames
threshold = 15           # More sensitive detection
min_area = 300          # Detect smaller movements
```

## 🆘 Getting Help

1. **Check logs**: `./docker-pi3b.sh logs`
2. **Verify system**: `./docker-pi3b.sh info`
3. **Test camera**: `raspistill -o test.jpg`
4. **Check permissions**: Ensure user is in `video` group
5. **Resource check**: Monitor CPU/memory usage

---

**Happy Motion Detecting with Docker! 🎥🐳**