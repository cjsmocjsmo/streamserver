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
    # Core Python runtime (essential)
    python3 \
    # OpenCV and computer vision (essential for motion detection)
    python3-opencv \
    python3-numpy \
    # Camera and video utilities (essential for camera access)
    v4l-utils \
    # Health check utility (essential for Docker health checks)
    curl \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get autoclean

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
    echo "Core packages verified from Debian system packages"

# Switch to non-root user
USER streamuser

# Expose HTTP port
EXPOSE 8000

# Health check specific to Pi 3B+
HEALTHCHECK --interval=30s --timeout=15s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start command
CMD ["python3", "streamserver.py"]