"""Dependency management and installation."""

import logging


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