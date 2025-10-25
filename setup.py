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
    """Install system packages via apt."""
    if not has_apt():
        print("Error: APT not available, cannot install system packages")
        print("Please install packages manually:")
        print("  - python3-opencv")
        print("  - python3-numpy") 
        print("  - python3-picamera2")
        return False
        
    system_packages = [
        'python3-opencv',
        'python3-numpy',
        'python3-picamera2'
    ]
    
    try:
        print("Installing system packages via apt...")
        subprocess.check_call(['sudo', 'apt', 'update'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        
        success = True
        for package in system_packages:
            try:
                subprocess.check_call(['sudo', 'apt', 'install', '-y', package], 
                                    stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL)
                print(f"✓ Installed {package}")
            except subprocess.CalledProcessError:
                print(f"✗ Could not install {package} via apt")
                success = False
                
        return success
        
    except subprocess.CalledProcessError as e:
        print(f"Error: APT update failed: {e}")
        return False


def main():
    """Install dependencies and setup the project."""
    print("Setting up Motion Detection Stream Server...")
    
    print(f"✓ Using Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Install system packages (apt only - no pip fallback)
    if not install_system_packages():
        print("\nWarning: Some packages could not be installed automatically.")
        print("Please run these commands manually:")
        print("  sudo apt update")
        print("  sudo apt install python3-opencv python3-numpy python3-picamera2")
    
    # Create necessary directories
    directories = ["recordings", "logs"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"Created directory: {directory}")
    
    print("\nSetup complete!")
    print("\nNext steps:")
    print("1. Run the server:")
    print("   python3 streamserver.py")
    print("\n2. Open your browser to:")
    print("   http://localhost:8000")
    print("\nNote: This project uses APT packages only (no pip/virtual env needed)")
    print("This complies with PEP 668 externally-managed-environment restrictions.")


if __name__ == "__main__":
    main()