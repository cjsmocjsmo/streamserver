# Raspberry Pi 3B+ Docker Dependencies

This document outlines the package strategy for the motion detection container, prioritizing Debian packages over pip installations.

## Package Priority Strategy

### 1. **Debian System Packages (Highest Priority)**
These packages are installed via `apt-get` and provide optimal performance on ARM architecture:

```bash
# Core Python environment
python3                    # Python 3 interpreter
python3-dev               # Development headers
python3-setuptools        # Package tools

# Computer Vision (Debian packages)
python3-opencv            # OpenCV with optimized ARM builds
libopencv-dev            # OpenCV development libraries
python3-numpy            # NumPy with optimized BLAS

# Camera Support (Pi-specific)
python3-picamera         # Original Pi camera library
python3-picamera2        # New Pi camera library
libcamera-dev            # Camera development libraries
libcamera-tools          # Camera utilities

# Hardware Acceleration (Pi 3B+ specific)
libraspberrypi-bin       # GPU utilities
libraspberrypi-dev       # GPU development libraries
libraspberrypi0          # GPU runtime libraries
```

### 2. **System Libraries (ARM Optimized)**
Pre-compiled libraries that avoid compilation on the Pi:

```bash
# Video/Media Processing
libavcodec58             # Video codec library
libavformat58            # Media format handling
libswscale5              # Video scaling
libswresample3           # Audio resampling

# Math Libraries (Optimized for ARM)
libatlas-base-dev        # Linear algebra (ARM optimized)
liblapack3               # Linear algebra routines
libblas3                 # Basic linear algebra

# Image Processing
libjpeg62-turbo-dev      # JPEG handling (ARM optimized)
libpng16-16              # PNG support
libtiff5-dev             # TIFF support
```

### 3. **pip3 (Last Resort Only)**
Only used for packages not available as Debian packages:

- Custom or very new packages
- Packages requiring specific versions not in Debian repos
- Pure Python packages without system dependencies

## Pi 3B+ Specific Optimizations

### Hardware Access
```dockerfile
# GPU Memory configuration
gpu_mem=128              # Allocate 128MB to GPU for camera

# Device access in container
/dev/video0              # Camera device
/dev/vchiq               # VideoCore GPU interface
/dev/vcsm                # VideoCore shared memory
/dev/gpiomem             # GPIO access
```

### Memory Management
```yaml
# Resource limits for 1GB RAM Pi 3B+
memory: 512M             # Maximum container memory
memory_reservation: 256M # Minimum guaranteed memory
```

### Library Paths
```bash
# System library paths
PYTHONPATH=/usr/lib/python3/dist-packages
LD_LIBRARY_PATH=/opt/vc/lib
```

## Benefits of This Approach

1. **Faster Installation**: No compilation needed on ARM
2. **Better Performance**: ARM-optimized binaries
3. **Smaller Image Size**: Shared system libraries
4. **More Stable**: Tested Debian package combinations
5. **Lower CPU Usage**: Optimized for Pi 3B+ architecture
6. **Better Memory Usage**: Efficient ARM implementations

## Package Verification

The Dockerfile includes verification steps:
```dockerfile
RUN python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" && \
    python3 -c "import numpy; print(f'NumPy version: {numpy.__version__}')" && \
    python3 -c "import picamera2; print('PiCamera2 available')"
```

This ensures all required packages are available from system sources before container startup.