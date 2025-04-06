# app/utils/logging.py
import logging
import sys
from app.config import settings

def setup_logging():
    """
    Set up basic logging configuration for the application.
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
    
    # Add file handler if specified in settings
    if hasattr(settings, 'LOG_FILE') and settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)

def get_logger(name):
    """
    Get a logger with the given name.
    
    Args:
        name: Usually __name__ to get the module name
    
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)