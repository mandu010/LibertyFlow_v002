# app/utils/logging.py
import logging
import sys
import os
from datetime import datetime

from app.config import settings

def setup_logging():
    """
    Set up basic logging configuration for the application with both console and file logging.
    """
    # Create basic formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    
    # Clear any existing handlers and add our console handler
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    
    # Create log directory if it doesn't exist
    log_dir = settings.LOG_DIR if hasattr(settings, 'LOG_DIR') and settings.LOG_DIR else "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"strategy_log_{timestamp}.log")
    
    # Create and add file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Still respect settings.LOG_FILE if it exists (for backward compatibility)
    if hasattr(settings, 'LOG_FILE') and settings.LOG_FILE:
        additional_file_handler = logging.FileHandler(settings.LOG_FILE)
        additional_file_handler.setFormatter(formatter)
        root_logger.addHandler(additional_file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Log the start of the application
    root_logger.info(f"Logging initialized, writing to: {log_file}")
    
    return log_file

def get_logger(name):
    """
    Get a logger with the given name.
    
    Args:
        name: Usually __name__ to get the module name
    
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)