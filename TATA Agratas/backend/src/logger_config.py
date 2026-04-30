"""
Centralized Logging Configuration for TATA Agratas RAG System
Provides structured logging with different levels and formatters
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Define log file paths
LOG_FILE = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"

# Custom formatter with colors for console
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # Format the message
        result = super().format(record)
        
        # Reset levelname for file logging
        record.levelname = levelname
        
        return result


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup and configure a logger with both file and console handlers
    
    Args:
        name: Logger name (usually __name__ of the module)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler for all logs
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Error file handler for errors and above
    error_handler = logging.FileHandler(ERROR_LOG_FILE, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    return logger


# Create a default logger for the application
app_logger = setup_logger('tata_agratas', level=logging.INFO)


# Utility functions for common logging patterns
def log_api_call(logger: logging.Logger, api_name: str, endpoint: str, **kwargs):
    """Log an API call with parameters"""
    params_str = ', '.join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"API Call: {api_name} | Endpoint: {endpoint} | Params: {params_str}")


def log_api_response(logger: logging.Logger, api_name: str, status_code: int, duration_ms: float):
    """Log an API response"""
    if status_code == 200:
        logger.info(f"API Response: {api_name} | Status: {status_code} | Duration: {duration_ms:.2f}ms")
    else:
        logger.warning(f"API Response: {api_name} | Status: {status_code} | Duration: {duration_ms:.2f}ms")


def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """Log an error with context"""
    logger.error(f"Error in {context}: {type(error).__name__}: {str(error)}", exc_info=True)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, threshold_ms: float = 1000):
    """Log performance metrics with warning if threshold exceeded"""
    if duration_ms > threshold_ms:
        logger.warning(f"Performance: {operation} took {duration_ms:.2f}ms (threshold: {threshold_ms}ms)")
    else:
        logger.debug(f"Performance: {operation} took {duration_ms:.2f}ms")


if __name__ == "__main__":
    # Test the logger
    test_logger = setup_logger('test', level=logging.DEBUG)
    test_logger.debug("This is a debug message")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")
    test_logger.critical("This is a critical message")
    print(f"\nLogs are being written to: {LOG_FILE}")
    print(f"Error logs are being written to: {ERROR_LOG_FILE}")

# Made with Bob