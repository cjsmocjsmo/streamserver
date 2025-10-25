"""Dependency management and installation."""

import logging
import subprocess
import sys
import os


def check_and_install_packages():
    """Check if required packages are installed, install if missing."""
    required_packages = {
        'cv2': {'apt': 'python3-opencv', 'pip': 'opencv-python'},
        'numpy': {'apt': 'python3-numpy', 'pip': 'numpy'}
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
        logging.warning(f"⚠️ Failed to install {apt_package} via apt: {e}")
        return False


def _install_with_pip(pip_package):
    """Install package using pip.
    
    Args:
        pip_package: pip package name to install
        
    Returns:
        bool: True if installation succeeded
    """
    try:
        logging.info(f"Installing {pip_package} via pip...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', pip_package
        ], capture_output=True, text=True)
        
        logging.info(f"✅ Successfully installed {pip_package} via pip")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to install {pip_package} via pip: {e}")
        return False


def _install_packages(packages):
    """Install missing packages, preferring apt over pip.
    
    Args:
        packages: List of package info dictionaries with 'apt' and 'pip' keys
        
    Raises:
        SystemExit: If package installation fails
    """
    logging.info("Installing missing packages...")
    has_apt = _has_apt()
    
    for package_info in packages:
        apt_package = package_info['apt']
        pip_package = package_info['pip']
        
        installed = False
        
        # Try apt first if available
        if has_apt:
            installed = _install_with_apt(apt_package)
        
        # Fall back to pip if apt failed or unavailable
        if not installed:
            if not _install_with_pip(pip_package):
                logging.error(f"❌ Failed to install {pip_package} with both apt and pip")
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