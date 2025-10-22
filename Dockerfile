# Dockerfile for Raspberry Pi 3B+ Motion Detection Stream Server
# Optimized for ARM architecture with Debian packages priority

FROM debian:trixie-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/site-packages

# Set labels
LABEL maintainer="Motion Detection Stream Server"
LABEL description="Raspberry Pi 3B+ optimized motion detection streaming server with Debian Trixie"
LABEL architecture="armv7l"

# Update package lists and install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    # Core Python runtime (no dev packages needed)
    python3 \
    python3-setuptools \
    python3-distutils \
    # OpenCV and computer vision (runtime packages only)
    python3-opencv \
    python3-numpy \
    # Camera support for Pi 3B+
    python3-picamera \
    python3-picamera2 \
    libcamera-tools \
    libcamera-apps \
    # Video4Linux and camera utilities
    v4l-utils \
    # GPU and hardware acceleration for Pi 3B+ (runtime only)
    libraspberrypi-bin \
    libraspberrypi0 \
    # Additional media libraries (runtime packages)
    libavcodec58 \
    libavformat58 \
    libavutil56 \
    libswscale5 \
    libswresample3 \
    # Math and optimization libraries (runtime only)
    liblapack3 \
    libblas3 \
    # Image processing support (runtime only)
    libjpeg62-turbo \
    libpng16-16 \
    libtiff5 \
    # Network and web server
    curl \
    wget \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get autoclean

# Enable GPU memory split for camera (Pi 3B+ specific)
RUN echo 'gpu_mem=128' >> /boot/config.txt 2>/dev/null || true

# Create application directory
WORKDIR /app

# Create non-root user with video group access
RUN useradd -m -u 1000 -G video,gpio streamuser && \
    mkdir -p /app/recordings /app/logs && \
    chown -R streamuser:streamuser /app

# Copy application files
COPY --chown=streamuser:streamuser streamserver.py .
COPY --chown=streamuser:streamuser motion_config.ini .

# Verify Python packages are available from Debian
RUN python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" && \
    python3 -c "import numpy; print(f'NumPy version: {numpy.__version__}')" && \
    python3 -c "import picamera2; print('PiCamera2 available')" && \
    echo "All required packages verified from system packages"

# Switch to non-root user
USER streamuser

# Expose HTTP port
EXPOSE 8000

# Health check specific to Pi 3B+
HEALTHCHECK --interval=30s --timeout=15s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start command
CMD ["python3", "streamserver.py"]