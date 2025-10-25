"""Dependency management and installation."""

import logging
import subprocess
import sys
import os


def check_and_install_packages():
    """Check if required packages are installed, install if missing."""
    required_packages = {
        'cv2': {'apt': 'python3-opencv'},
        'numpy': {'apt': 'python3-numpy'}
    }
    
    missing_packages = []
    
    for module, package_info in required_packages.items():
        try:
            __import__(module)
            logging.info(f"✅ {module} is available")
        except ImportError:
            logging.warning(f"❌ {module} not found")
            missing_packages.append(package_info)
    
    if missing_packages:
        _install_packages(missing_packages)


def _has_apt():
    """Check if apt package manager is available."""
    try:
        subprocess.check_call(['which', 'apt'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def _install_with_apt(apt_package):
    """Install package using apt.
    
    Args:
        apt_package: APT package name to install
        
    Returns:
        bool: True if installation succeeded
    """
    try:
        logging.info(f"Installing {apt_package} via apt...")
        subprocess.check_call([
            'sudo', 'apt', 'update'
        ], capture_output=True, text=True)
        
        subprocess.check_call([
            'sudo', 'apt', 'install', '-y', apt_package
        ], capture_output=True, text=True)
        
        logging.info(f"✅ Successfully installed {apt_package} via apt")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to install {apt_package} via apt: {e}")
        return False


def _install_packages(packages):
    """Install missing packages using apt only.
    
    Args:
        packages: List of package info dictionaries with 'apt' keys
        
    Raises:
        SystemExit: If package installation fails
    """
    logging.info("Installing missing packages...")
    has_apt = _has_apt()
    
    if not has_apt:
        logging.error("❌ APT package manager not available")
        logging.error("❌ Cannot install required packages")
        logging.error("Please install packages manually:")
        for package_info in packages:
            logging.error(f"   - {package_info['apt']}")
        sys.exit(1)
    
    for package_info in packages:
        apt_package = package_info['apt']
        
        if not _install_with_apt(apt_package):
            logging.error(f"❌ Failed to install {apt_package}")
            logging.error("Please install manually:")
            logging.error(f"   sudo apt install {apt_package}")
            sys.exit(1)


def verify_picamera2():
    """Verify Picamera2 is available.
    
    Returns:
        bool: True if Picamera2 is available
    """
    try:
        from picamera2 import Picamera2
        logging.info("✅ Picamera2 is available")
        return True
    except ImportError as e:
        logging.error(f"❌ Picamera2 not available: {e}")
        logging.error("Please install picamera2: sudo apt install python3-picamera2")
        return False