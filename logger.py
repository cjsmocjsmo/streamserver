"""Logging configuration for the stream server."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(level=logging.INFO, log_file=None, log_dir="logs"):
    """Set up logging configuration.
    
    Args:
        level: Logging level (default: INFO)
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
    
    # Configure logging format
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_filepath, mode='a')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    logging.info(f"📝 Logging initialized - File: {log_filepath}")


def get_logger(name):
    """Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)