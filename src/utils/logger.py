"""Logging configuration for Draft Maker application."""

import logging
import sys
from typing import Optional
import json
from datetime import datetime
from google.cloud import firestore
from src.config import settings, is_production
import re


class CredentialSanitizerFilter(logging.Filter):
    """Filter to sanitize sensitive credentials from log messages."""

    def filter(self, record):
        """Filter and sanitize log records."""
        # Patterns to sanitize
        patterns = [
            # Discogs API credentials in URLs
            (r"key=[^&\s]+", "key=***REDACTED***"),
            (r"secret=[^&\s]+", "secret=***REDACTED***"),
            # OAuth tokens
            (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***REDACTED***"),
            (r"access_token=[^&\s]+", "access_token=***REDACTED***"),
            (r"refresh_token=[^&\s]+", "refresh_token=***REDACTED***"),
            # API keys in various formats
            (r"api_key=[^&\s]+", "api_key=***REDACTED***"),
            (r"apikey=[^&\s]+", "apikey=***REDACTED***"),
            # eBay specific
            (r"SECURITY-APPNAME=[^&\s]+", "SECURITY-APPNAME=***REDACTED***"),
        ]

        # Sanitize the message
        if hasattr(record, "msg"):
            msg = str(record.msg)
            for pattern, replacement in patterns:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg

        # Also sanitize args if present
        if hasattr(record, "args") and record.args:
            sanitized_args = []
            for arg in record.args:
                arg_str = str(arg)
                for pattern, replacement in patterns:
                    arg_str = re.sub(pattern, replacement, arg_str, flags=re.IGNORECASE)
                sanitized_args.append(arg_str)
            record.args = tuple(sanitized_args)

        return True


class CloudRunFormatter(logging.Formatter):
    """Custom formatter for Cloud Run structured logging."""

    def format(self, record):
        """Format log record for Cloud Run."""
        log_obj = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.utcnow().isoformat(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add any extra fields
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id

        if hasattr(record, "upc"):
            log_obj["upc"] = record.upc

        if hasattr(record, "api"):
            log_obj["api"] = record.api

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration for the application.

    Args:
        log_level: Override log level (default from settings)

    Returns:
        Root logger instance
    """
    level = log_level or settings.log_level

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Use structured logging for production
    if is_production():
        formatter = CloudRunFormatter()
    else:
        # Use readable format for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)

    # Add credential sanitizer filter to the handler
    sanitizer_filter = CredentialSanitizerFilter()
    console_handler.addFilter(sanitizer_filter)

    # Configure root logger
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    # Set httpx to WARNING to suppress HTTP request logs that might contain credentials
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class FirestoreLogHandler:
    """Handler for logging to Firestore."""

    def __init__(self):
        """Initialize Firestore client."""
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.collection = settings.firestore_collection_logs

    async def log_processing(
        self,
        correlation_id: str,
        upc: str,
        stage: str,
        status: str,
        message: str,
        metadata: Optional[dict] = None,
    ):
        """
        Log processing information to Firestore.

        Args:
            correlation_id: Unique ID for this processing run
            upc: UPC being processed
            stage: Processing stage (metadata_fetch, image_fetch, etc.)
            status: Status (started, completed, failed)
            message: Log message
            metadata: Additional metadata to log
        """
        doc_data = {
            "correlation_id": correlation_id,
            "upc": upc,
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow(),
            "environment": settings.environment,
        }

        if metadata:
            doc_data["metadata"] = metadata

        try:
            self.db.collection(self.collection).add(doc_data)
        except Exception as e:
            # Don't fail the main process if logging fails
            logger = get_logger(__name__)
            logger.error(f"Failed to log to Firestore: {e}")


# Initialize logging on module import
setup_logging()
