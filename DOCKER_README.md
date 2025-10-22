# 🍓 Raspberry Pi 3B+ Motion Detection Docker Guide

A containerized motion detection stream server specifically optimized for Raspberry Pi 3B+ with Debian package priority.

## 🚀 Quick Start

### 1. Prerequisites - Rootless Docker Installation

#### Install Required System Packages
```bash
# Update system packages
sudo apt-get update

# Install prerequisites for rootless Docker
sudo apt-get install -y \
    curl \
    uidmap \
    dbus-user-session \
    fuse-overlayfs \
    slirp4netns

# Install additional packages for Pi camera and hardware access
sudo apt-get install -y \
    v4l-utils \
    runc \
    containerd \
    systemd-container
```

#### Install Rootless Docker
```bash
# Download and install rootless Docker
curl -fsSL https://get.docker.com/rootless | sh

# Add Docker binaries to PATH (add to ~/.bashrc for persistence)
export PATH=/home/$USER/bin:$PATH
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock

# Enable systemd user service
systemctl --user enable docker
systemctl --user start docker

# Verify installation
docker version
```

#### Install Docker Compose (Debian Package Priority)
```bash
# Install docker-compose from Debian repositories (preferred method)
sudo apt-get install -y docker-compose

# Verify docker-compose installation
docker-compose --version

# If Debian package is not available or too old, use standalone binary as fallback
# sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
# sudo chmod +x /usr/local/bin/docker-compose

# Only use pip3 as absolute last resort if both above methods fail:
# pip3 install --user docker-compose
```

#### Configure Rootless Environment
```bash
# Add to ~/.bashrc for automatic setup
echo 'export PATH=/home/$USER/bin:$PATH' >> ~/.bashrc
echo 'export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock' >> ~/.bashrc

# Configure systemd for rootless containers
loginctl enable-linger $USER

# Source the updated bashrc
source ~/.bashrc
```

#### Hardware Access Configuration (Pi 3B+ Specific)
```bash
# Add user to required groups for hardware access
sudo usermod -a -G video $USER
sudo usermod -a -G gpio $USER

# Configure udev rules for rootless camera access
echo 'SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"' | sudo tee /etc/udev/rules.d/99-camera-rootless.rules
echo 'SUBSYSTEM=="vchiq", GROUP="video", MODE="0664"' | sudo tee -a /etc/udev/rules.d/99-camera-rootless.rules

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Ensure camera permissions
sudo chmod 664 /dev/video0 2>/dev/null || true
sudo chmod 664 /dev/vchiq 2>/dev/null || true

# Log out and log back in for group changes to take effect
echo "Please log out and log back in for all changes to take effect"
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

# Rootless Docker system logs
journalctl --user -u docker -f

# Check rootless Docker daemon status
systemctl --user status docker
```

## 🔧 Troubleshooting

### Rootless Docker Issues

#### Docker Daemon Not Running
```bash
# Check rootless Docker daemon status
systemctl --user status docker

# Start rootless Docker daemon
systemctl --user start docker

# Enable automatic startup
systemctl --user enable docker

# Check if DOCKER_HOST is set correctly
echo $DOCKER_HOST
# Should show: unix:///run/user/$(id -u)/docker.sock
```

#### Environment Variables Not Set
```bash
# Set Docker environment for current session
export PATH=/home/$USER/bin:$PATH
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock

# Add to ~/.bashrc permanently
echo 'export PATH=/home/$USER/bin:$PATH' >> ~/.bashrc
echo 'export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock' >> ~/.bashrc
source ~/.bashrc
```

#### Permission Issues with Hardware
```bash
# Check user groups
groups $USER

# Ensure user is in required groups
sudo usermod -a -G video,gpio $USER

# Check device permissions
ls -la /dev/video* /dev/vchiq /dev/gpiomem

# Fix device permissions if needed
sudo chmod 664 /dev/video0
sudo chmod 664 /dev/vchiq
sudo chmod 664 /dev/gpiomem
```

### Camera Not Detected
```bash
# Check camera device
ls -la /dev/video*

# Test camera (rootless compatible)
docker run --rm --device /dev/video0 -v /tmp:/tmp alpine:latest ls -la /dev/video0

# Verify user permissions
groups $USER | grep video

# Check if camera is in use by another process
sudo lsof /dev/video0
```

### Container Won't Start
```bash
# Check container logs (rootless)
docker logs motion-detection-pi3b

# Verify rootless Docker daemon
systemctl --user status docker

# Check if Docker socket is accessible
ls -la /run/user/$(id -u)/docker.sock

# Verify environment variables
echo "DOCKER_HOST: $DOCKER_HOST"
echo "PATH: $PATH"

# Check system resources
free -h && df -h

# Test basic Docker functionality
docker run --rm hello-world
```

### Rootless Docker Networking Issues
```bash
# Check if slirp4netns is working
ps aux | grep slirp4netns

# Test container networking
docker run --rm alpine:latest ping -c 3 8.8.8.8

# Check port binding (rootless uses different ports)
ss -tulpn | grep :8000

# If port conflicts, use different port
docker-compose down
# Edit docker-compose.yml to use different port like 8080:8000
docker-compose up -d
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

## 🔒 Rootless Docker Security Benefits

### Enhanced Security Features
- **No root privileges**: Docker daemon runs as regular user
- **Namespace isolation**: Better process isolation
- **Reduced attack surface**: No privileged Docker daemon
- **User-specific containers**: Each user has separate Docker environment

### Rootless Limitations & Workarounds
```bash
# Limited port range (>= 1024 only)
# Workaround: Use port 8000 (already > 1024) or map to higher port

# Some system calls restricted
# Workaround: Use --privileged flag only when necessary for hardware access

# Performance may be slightly lower
# Workaround: Use native networking when possible
```

### Hardware Access Configuration
- Camera and GPU access configured through user groups
- Device permissions managed via udev rules
- Configuration mounted read-only for security
- No unnecessary network exposure

## 🔧 Rootless Docker Management

### Service Management
```bash
# Start/stop rootless Docker daemon
systemctl --user start docker
systemctl --user stop docker
systemctl --user restart docker

# Enable automatic startup after login
systemctl --user enable docker
loginctl enable-linger $USER

# Check daemon status
systemctl --user status docker
```

### Environment Setup
```bash
# Check current rootless setup
docker context ls
docker info | grep -i rootless

# Reset environment if needed
unset DOCKER_HOST
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
```

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

## ✅ Rootless Docker Verification

### Quick Setup Verification
```bash
# 1. Verify rootless Docker installation
docker version | grep -A5 "Server:"
# Should show rootless engine

# 2. Test basic container functionality  
docker run --rm hello-world

# 3. Check environment variables
echo "DOCKER_HOST: $DOCKER_HOST"
echo "PATH contains user bin: $(echo $PATH | grep -o '/home/[^:]*bin')"

# 4. Verify hardware access
ls -la /dev/video* /dev/vchiq
groups $USER | grep -E "(video|gpio)"

# 5. Test camera access in container
docker run --rm --device /dev/video0 alpine:latest ls -la /dev/video0
```

### Complete System Test
```bash
# Run full system test
./docker-pi3b.sh info

# Build and test the motion detection container
./docker-pi3b.sh build

# Start the service
./docker-pi3b.sh run

# Verify web interface is accessible
curl -I http://localhost:8000
```

## 🆘 Getting Help

### Rootless Docker Specific Issues
1. **Check rootless daemon**: `systemctl --user status docker`
2. **Verify environment**: Check `DOCKER_HOST` and `PATH` variables
3. **Test basic functionality**: `docker run --rm hello-world`
4. **Check user groups**: Ensure user is in `video` and `gpio` groups
5. **Hardware permissions**: Verify `/dev/video0` and `/dev/vchiq` access

### General Troubleshooting
1. **Check logs**: `./docker-pi3b.sh logs`
2. **Verify system**: `./docker-pi3b.sh info`
3. **Test camera**: `docker run --rm --device /dev/video0 alpine ls -la /dev/video0`
4. **Resource check**: Monitor CPU/memory usage with `docker stats`
5. **Network test**: `docker run --rm alpine ping -c 3 8.8.8.8`

### Common Rootless Docker Commands
```bash
# Restart everything
systemctl --user restart docker
./docker-pi3b.sh restart

# Reset environment
source ~/.bashrc
./docker-pi3b.sh info

# Complete reinstall if needed
./docker-pi3b.sh cleanup
# Follow installation steps again
```

---

**Happy Motion Detecting with Docker! 🎥🐳**