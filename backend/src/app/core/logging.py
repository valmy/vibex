"""
Logging configuration for the AI Trading Agent application.

Provides structured JSON logging with support for multiple log files,
log rotation, and sensitive data masking.
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime
from typing import Any, Dict


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in logs."""

    SENSITIVE_KEYS = {
        "api_key",
        "api_secret",
        "password",
        "private_key",
        "mnemonic",
        "secret",
        "token",
        "authorization",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in log records."""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._mask_sensitive_data(record.msg)
        if hasattr(record, "args") and isinstance(record.args, dict):
            record.args = self._mask_dict(record.args)
        return True

    def _mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive data in text."""
        for key in self.SENSITIVE_KEYS:
            if key.lower() in text.lower():
                text = text.replace(text, f"***MASKED***")
        return text

    def _mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in dictionary."""
        masked = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_dict(value)
            else:
                masked[key] = value
        return masked


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data["context"] = record.extra_data

        return json.dumps(log_data)


def setup_logging(config: Any) -> None:
    """
    Set up logging configuration.

    Args:
        config: Configuration object with logging settings
    """
    # Create logs directory if it doesn't exist
    os.makedirs(config.LOG_DIR, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    console_handler.addFilter(sensitive_filter)

    if config.LOG_FORMAT == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handlers for different log types
    log_files = {
        "app": "app.log",
        "trading": "trading.log",
        "market_data": "market_data.log",
        "llm": "llm.log",
        "errors": "errors.log",
    }

    for log_type, filename in log_files.items():
        log_path = os.path.join(config.LOG_DIR, filename)

        # Rotating file handler (100MB per file, 10 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
        )

        file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        file_handler.addFilter(sensitive_filter)

        if config.LOG_FORMAT == "json":
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        file_handler.setFormatter(file_formatter)

        # Create logger for specific log type
        logger = logging.getLogger(log_type)
        logger.addHandler(file_handler)
        logger.setLevel(getattr(logging, config.LOG_LEVEL))


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)
