"""Logging configuration with structured logging support."""

import sys
import logging
from pathlib import Path
from typing import Optional, Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
from prometheus_client import Counter, Histogram, Gauge, Info

from .config import Settings


# Prometheus metrics
MESSAGES_RECEIVED = Counter(
    'gpgga_messages_received_total',
    'Total number of GPGGA messages received'
)

MESSAGES_PARSED = Counter(
    'gpgga_messages_parsed_total',
    'Total number of GPGGA messages successfully parsed'
)

PARSE_ERRORS = Counter(
    'gpgga_parse_errors_total',
    'Total number of GPGGA parse errors'
)

COT_CONVERSIONS = Counter(
    'cot_conversions_total',
    'Total number of successful CoT conversions'
)

COT_SENT = Counter(
    'cot_messages_sent_total',
    'Total number of CoT messages sent to TAK'
)

COT_SEND_ERRORS = Counter(
    'cot_send_errors_total',
    'Total number of errors sending CoT to TAK'
)

MESSAGE_PROCESSING_TIME = Histogram(
    'message_processing_seconds',
    'Time to process a GPGGA message to CoT',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

ACTIVE_DEVICES = Gauge(
    'active_devices_count',
    'Number of devices seen in the last period'
)

TAK_CONNECTION_STATUS = Gauge(
    'tak_connection_status',
    'TAK server connection status (1=connected, 0=disconnected)'
)

APP_INFO = Info(
    'gpgga_cot_relay',
    'Application information'
)


def setup_logging(settings: Settings) -> None:
    """
    Configure structured logging with structlog.
    
    Args:
        settings: Application settings
    """
    # Set up stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level)
    )
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_app_context,
    ]
    
    # Add appropriate renderer based on format
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set up file logging if configured
    if settings.log_file:
        setup_file_logging(settings.log_file, settings.log_level)
    
    # Set application info metric
    APP_INFO.info({
        'version': '1.0.0',
        'tak_server': settings.tak_server_url,
        'udp_port': str(settings.udp_listen_port),
        'device_type': settings.device_type
    })


def setup_file_logging(log_file: str, log_level: str) -> None:
    """
    Set up file-based logging.
    
    Args:
        log_file: Path to log file
        log_level: Logging level
    """
    try:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file handler with rotation
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        
        file_handler.setLevel(getattr(logging, log_level))
        
        # Add formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to root logger
        logging.getLogger().addHandler(file_handler)
        
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.error("Failed to setup file logging",
                    log_file=log_file,
                    error=str(e))


def add_app_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add application context to all log messages.
    
    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary
        
    Returns:
        Modified event dictionary
    """
    event_dict['app'] = 'gpgga-cot-relay'
    return event_dict


class ErrorHandler:
    """Centralized error handling with metrics and logging."""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.error_counts: Dict[str, int] = {}
        
    def handle_parse_error(self, message: str, error: Exception, sender: Optional[tuple] = None) -> None:
        """Handle GPGGA parse errors."""
        PARSE_ERRORS.inc()
        self.error_counts['parse'] = self.error_counts.get('parse', 0) + 1
        
        self.logger.warning("GPGGA parse error",
                          message=message,
                          error=str(error),
                          error_type=type(error).__name__,
                          sender=sender)
    
    def handle_conversion_error(self, device_id: str, error: Exception) -> None:
        """Handle CoT conversion errors."""
        self.error_counts['conversion'] = self.error_counts.get('conversion', 0) + 1
        
        self.logger.error("CoT conversion error",
                         device_id=device_id,
                         error=str(error),
                         error_type=type(error).__name__)
    
    def handle_send_error(self, device_id: str, error: Exception) -> None:
        """Handle TAK send errors."""
        COT_SEND_ERRORS.inc()
        self.error_counts['send'] = self.error_counts.get('send', 0) + 1
        
        self.logger.error("TAK send error",
                         device_id=device_id,
                         error=str(error),
                         error_type=type(error).__name__)
    
    def handle_connection_error(self, error: Exception) -> None:
        """Handle TAK connection errors."""
        TAK_CONNECTION_STATUS.set(0)
        self.error_counts['connection'] = self.error_counts.get('connection', 0) + 1
        
        self.logger.error("TAK connection error",
                         error=str(error),
                         error_type=type(error).__name__)
    
    def get_error_stats(self) -> Dict[str, int]:
        """Get error statistics."""
        return self.error_counts.copy()
    
    def reset_stats(self) -> None:
        """Reset error statistics."""
        self.error_counts.clear()


# Global error handler instance
error_handler = ErrorHandler()
