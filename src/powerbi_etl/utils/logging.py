"""
Structured logging configuration for Power BI ETL pipelines.
"""

import sys
import structlog
from typing import Any, Dict, Optional
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    format: str = "json",  # json or console
    output_file: Optional[str] = None,
) -> None:
    """
    Configure structlog for structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format (json or console)
        output_file: Optional file path for log output
    """
    import logging
    
    # Standard library logging setup
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Processors for structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # If output file specified, add file handler
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(output_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def add_context(**kwargs: Any) -> structlog.BoundLogger:
    """Add context to current logger."""
    return structlog.get_logger().bind(**kwargs)