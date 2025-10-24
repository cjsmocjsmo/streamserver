"""Dependency management and installation."""

import logging
import subprocess
import sys


def check_and_install_packages():
    """Check if required packages are installed, install if missing."""
    required_packages = {
        'cv2': 'opencv-python',
        'numpy': 'numpy'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
            logging.info(f"✅ {module} is available")
        except ImportError:
            logging.warning(f"❌ {module} not found, will install {package}")
            missing_packages.append(package)
    
    if missing_packages:
        _install_packages(missing_packages)


def _install_packages(packages):
    """Install missing packages using pip.
    
    Args:
        packages: List of package names to install
        
    Raises:
        SystemExit: If package installation fails
    """
    logging.info("Installing missing packages...")
    for package in packages:
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', package
            ], capture_output=True, text=True)
            logging.info(f"✅ Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Failed to install {package}: {e}")
            logging.error(f"STDOUT: {e.stdout}")
            logging.error(f"STDERR: {e.stderr}")
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