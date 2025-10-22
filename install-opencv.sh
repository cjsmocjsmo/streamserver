#!/bin/bash

# OpenCV Motion Detection Setup Script
echo "Setting up OpenCV Motion Detection Stream Server..."

# Check if we're on Raspberry Pi
if [[ $(uname -m) == "arm"* ]] || [[ $(uname -m) == "aarch64" ]]; then
    echo "Detected Raspberry Pi ARM architecture"
    ARM_PLATFORM=true
else
    echo "Detected x86/x64 architecture"
    ARM_PLATFORM=false
fi

# Update system packages
echo "Updating system packages..."
sudo apt update

# Install system dependencies for OpenCV
echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    libopencv-dev \
    python3-opencv \
    libatlas-base-dev \
    libjasper-dev \
    libqtgui4 \
    libqt4-test \
    libhdf5-dev \
    libhdf5-serial-dev \
    libharfbuzz0b \
    libwebp6 \
    libtiff5 \
    libjasper1 \
    libilmbase25 \
    libopenexr25 \
    libgstreamer1.0-0 \
    libavcodec58 \
    libavformat58 \
    libswscale5 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo "Installing Python dependencies..."
if [ "$ARM_PLATFORM" = true ]; then
    # For Raspberry Pi, use system OpenCV to avoid compilation issues
    echo "Installing packages for Raspberry Pi..."
    pip install numpy
    # Use system OpenCV package
    echo "Using system OpenCV installation for ARM platform"
else
    # For x86/x64, install OpenCV from pip
    echo "Installing packages for x86/x64..."
    pip install -r requirements.txt
fi

# Create recordings directory
echo "Creating recordings directory..."
mkdir -p recordings

# Set permissions
echo "Setting permissions..."
chmod +x install-opencv.sh

echo ""
echo "✅ OpenCV Motion Detection setup complete!"
echo ""
echo "To run the motion detection server:"
echo "  source venv/bin/activate"
echo "  python3 streamserver.py"
echo ""
echo "Configuration:"
echo "  - Edit motion_config.ini to adjust detection settings"
echo "  - Recordings will be saved in the 'recordings' directory"
echo "  - Stream available at http://localhost:8000"
echo ""
echo "Features:"
echo "  ✅ Real-time motion detection"
echo "  ✅ 5-second pre-recording buffer"
echo "  ✅ Automatic recording start/stop"
echo "  ✅ Configurable sensitivity"
echo "  ✅ MP4 video output"