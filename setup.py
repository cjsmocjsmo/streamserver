#!/usr/bin/env python3
"""Setup script for Motion Detection Stream Server."""

import sys
import subprocess
from pathlib import Path


def has_apt():
    """Check if apt package manager is available."""
    try:
        subprocess.check_call(['which', 'apt'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def install_system_packages():
    """Install system packages via apt if available."""
    if not has_apt():
        print("� APT not available, skipping system package installation")
        return
        
    system_packages = [
        'python3-opencv',
        'python3-numpy',
        'python3-picamera2'
    ]
    
    try:
        print("📦 Installing system packages via apt...")
        subprocess.check_call(['sudo', 'apt', 'update'], 
                            capture_output=True, text=True)
        
        for package in system_packages:
            try:
                subprocess.check_call(['sudo', 'apt', 'install', '-y', package], 
                                    capture_output=True, text=True)
                print(f"✅ Installed {package}")
            except subprocess.CalledProcessError:
                print(f"⚠️ Could not install {package} via apt")
                
    except subprocess.CalledProcessError as e:
        print(f"⚠️ APT update failed: {e}")


def install_pip_fallbacks():
    """Install packages via pip that weren't available via apt."""
    requirements_file = Path(__file__).parent / "requirements.txt"
    if requirements_file.exists():
        print("📦 Installing remaining dependencies via pip...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            print("✅ Pip dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install pip dependencies: {e}")


def main():
    """Install dependencies and setup the project."""
    print("🚀 Setting up Motion Detection Stream Server...")
    
    print(f"✅ Using Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Install system packages first (preferred)
    install_system_packages()
    
    # Install any remaining packages via pip
    install_pip_fallbacks()
    
    # Create necessary directories
    directories = ["recordings", "logs"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Run the server:")
    print("   python3 streamserver_v2.py")
    print("\n2. Open your browser to:")
    print("   http://localhost:8000")


if __name__ == "__main__":
    main()