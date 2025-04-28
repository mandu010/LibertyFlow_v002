import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

class PostgresSettings(BaseSettings):
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "H59IE0C7SM-100")
    PORT: int = int(os.getenv("POSTGRES_PORT") or 5432)
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POOL_MIN_SIZE: int = int(os.getenv("POSTGRES_POOL_MIN_SIZE"))
    POOL_MAX_SIZE: int = int(os.getenv("POSTGRES_POOL_MAX_SIZE"))

    model_config = {
        "extra": "ignore"
    }    
    
class FyersSettings(BaseSettings):
    CLIENT_ID: str = os.getenv("FYERS_APP_ID")
    SECRET_KEY: str = os.getenv("FYERS_APP_SECRET")
    REDIRECT_URI: str = os.getenv("FYERS_REDIRECT_URI")
    FYERS_USERNAME: str = os.getenv("FYERS_USERNAME")
    FYERS_PASSWORD: str = os.getenv("FYERS_PASSWORD")
    FYERS_GRANT_TYPE: str = os.getenv("FYERS_GRANT_TYPE")
    FYERS_AUTHORIZATION_TOKEN: str = os.getenv("FYERS_AUTHORIZATION_TOKEN")
    FYERS_ACCESS_TOKEN: str = os.getenv("FYERS_ACCESS_TOKEN")

    model_config = {
        "extra": "ignore"
    }   

class TradeSettings(BaseSettings):
    NIFTY_LOT: int = int(os.getenv("NIFTY_LOT"))
    NIFTY_LOT_SIZE: int = int(os.getenv("NIFTY_LOT_SIZE"))
    NIFTY_SYMBOL: str = os.getenv("NIFTY_SYMBOL")

    model_config = {
        "extra": "ignore"
    }       

class SlackSettings(BaseSettings):
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN")
    SLACK_NIFTY_STATUS_WEBHOOK: str = os.getenv("SLACK_NIFTY_STATUS_WEBHOOK")

    model_config = {
        "extra": "ignore"
    }       

class AppSettings(BaseSettings):
    """Application-wide settings."""
    # General settings
    APP_NAME: str = os.getenv("APP_NAME")
    APP_VERSION: str = os.getenv("APP_VERSION")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", None)
    
    # Nested settings
    postgres: PostgresSettings = PostgresSettings()
    fyers: FyersSettings = FyersSettings()
    trade: TradeSettings = TradeSettings()
    slack: SlackSettings = SlackSettings()
    
    # Performance settings
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "10"))
    
    # Feature flags
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "False").lower() in ("true", "1", "t")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }


# Create a global settings object
settings = AppSettings()

def get_logger(name: str) -> logging.Logger:
    """Configure and return a logger with the given name."""
    log_level = getattr(logging, settings.LOG_LEVEL)
    
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(settings.LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if LOG_FILE is specified
    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(settings.LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger