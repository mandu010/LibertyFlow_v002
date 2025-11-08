# app/utils/logging.py
import logging
import sys
import os
from datetime import datetime

from app.config import settings

# Global registry to track strategy-specific handlers
_strategy_handlers = {}

class StrategyFilter(logging.Filter):
    """Filter logs based on strategy name"""
    def __init__(self, strategy_name):
        super().__init__()
        self.strategy_name = strategy_name

    def filter(self, record):
        # Only allow logs that match this strategy or have no strategy specified (default to nifty)
        record_strategy = getattr(record, 'strategy', 'nifty')
        return record_strategy == self.strategy_name

class StrategyAdapter(logging.LoggerAdapter):
    """Adapter to automatically add strategy context to log records"""
    def __init__(self, logger, strategy_name):
        super().__init__(logger, {'strategy': strategy_name})
        self.strategy_name = strategy_name

    def process(self, msg, kwargs):
        # Inject strategy into extra dict
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['strategy'] = self.strategy_name
        return msg, kwargs

def setup_logging(strategy_name='nifty', log_dir=None):
    """
    Set up logging configuration for the application with both console and file logging.

    Args:
        strategy_name: Name of the strategy ('nifty', 'banknifty', etc.). Defaults to 'nifty'.
        log_dir: Custom log directory. If None, uses automatic directory based on strategy.

    Returns:
        Path to the created log file

    Examples:
        # For Nifty (existing code - no changes needed)
        setup_logging()  # Logs to logs/

        # For BankNifty (new code)
        setup_logging(strategy_name='banknifty')  # Logs to logs/LibertyMomentum_BNF/
    """
    # Create basic formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # For the default 'nifty' strategy, clear handlers (original behavior)
    if strategy_name == 'nifty' and not root_logger.handlers:
        root_logger.handlers = []

    # Create and add console handler (enabled for all strategies by default)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Only add console handler if it doesn't already exist (avoid duplicates)
    has_console_handler = any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)
    if not has_console_handler:
        root_logger.addHandler(console_handler)

    # Determine log directory
    if log_dir is None:
        if strategy_name == 'nifty':
            log_dir = settings.LOG_DIR if hasattr(settings, 'LOG_DIR') and settings.LOG_DIR else "logs"
        else:
            # For other strategies, create strategy-specific subdirectory
            base_dir = settings.LOG_DIR if hasattr(settings, 'LOG_DIR') and settings.LOG_DIR else "logs"
            log_dir = os.path.join(base_dir, f"LibertyMomentum_{strategy_name.upper()}")

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"strategy_log_{timestamp}.log")

    # Create and add file handler with strategy filter
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Add strategy filter to ensure only logs for this strategy go to this file
    strategy_filter = StrategyFilter(strategy_name)
    file_handler.addFilter(strategy_filter)

    # Store handler in global registry for this strategy
    _strategy_handlers[strategy_name] = file_handler

    # Add file handler to root logger
    root_logger.addHandler(file_handler)

    # Still respect settings.LOG_FILE if it exists (for backward compatibility) - only for nifty
    if strategy_name == 'nifty' and hasattr(settings, 'LOG_FILE') and settings.LOG_FILE:
        additional_file_handler = logging.FileHandler(settings.LOG_FILE)
        additional_file_handler.setFormatter(formatter)
        additional_filter = StrategyFilter('nifty')
        additional_file_handler.addFilter(additional_filter)
        root_logger.addHandler(additional_file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Log the start of the application
    root_logger.info(f"Logging initialized for {strategy_name}, writing to: {log_file}", extra={'strategy': strategy_name})

    return log_file

def get_logger(name, strategy_name=None):
    """
    Get a logger with the given name, optionally wrapped with strategy context.

    Args:
        name: Usually __name__ to get the module name
        strategy_name: Optional strategy name ('nifty', 'banknifty').
                      If provided, returns a StrategyAdapter that automatically tags all logs.

    Returns:
        A configured logger instance or StrategyAdapter

    Examples:
        # For Nifty (existing code - no changes needed)
        logger = get_logger("MAIN")
        logger.info("Starting")  # Auto-tagged with strategy='nifty'

        # For BankNifty (new code)
        logger = get_logger("MAIN", strategy_name='banknifty')
        logger.info("Starting")  # Auto-tagged with strategy='banknifty'
    """
    logger = logging.getLogger(name)

    # If strategy_name is provided, wrap in adapter for automatic tagging
    if strategy_name:
        return StrategyAdapter(logger, strategy_name)

    # Default to 'nifty' strategy for backward compatibility
    return StrategyAdapter(logger, 'nifty')