"""Logging configuration for the stream server."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(level=logging.DEBUG, log_file=None, log_dir="logs"):
    """Set up comprehensive logging configuration.
    
    Args:
        level: Logging level (default: DEBUG to catch all errors)
        log_file: Optional log file name (default: auto-generated)
        log_dir: Directory for log files (default: "logs")
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Generate log filename if not provided
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"streamserver_{timestamp}.log"
    
    log_filepath = log_path / log_file
    
    # Configure detailed logging format
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (INFO and above for readability)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (DEBUG and above for comprehensive logging)
    file_handler = logging.FileHandler(log_filepath, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (ERROR and above for critical issues)
    error_log_filepath = log_path / f"errors_{timestamp}.log"
    error_handler = logging.FileHandler(error_log_filepath, mode='a')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Capture uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception
    
    logging.info(f"📝 Comprehensive logging initialized")
    logging.info(f"📁 Main log: {log_filepath}")
    logging.info(f"🚨 Error log: {error_log_filepath}")
    logging.debug("🔍 Debug logging enabled - all errors will be captured")


def get_logger(name):
    """Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)