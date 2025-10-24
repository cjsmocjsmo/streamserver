#!/usr/bin/env python3
"""Setup script for Motion Detection Stream Server."""

import sys
import subprocess
from pathlib import Path


def main():
    """Install dependencies and setup the project."""
    print("🚀 Setting up Motion Detection Stream Server...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install requirements
    requirements_file = Path(__file__).parent / "requirements.txt"
    if requirements_file.exists():
        print("📦 Installing Python dependencies...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            sys.exit(1)
    
    # Create necessary directories
    directories = ["recordings", "logs"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. On Raspberry Pi, install picamera2:")
    print("   sudo apt update && sudo apt install python3-picamera2")
    print("\n2. Run the server:")
    print("   python3 streamserver_v2.py")
    print("\n3. Open your browser to:")
    print("   http://localhost:8000")


if __name__ == "__main__":
    main()