"""Configuration management using environment variables."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, AnyUrl


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # UDP Listener Configuration
    udp_listen_host: str = Field(
        default="0.0.0.0",
        description="Host to bind UDP listener to"
    )
    udp_listen_port: int = Field(
        default=5005,
        ge=1,
        le=65535,
        description="Port to listen for GPGGA messages"
    )
    udp_buffer_size: int = Field(
        default=1024,
        ge=256,
        le=65536,
        description="UDP receive buffer size in bytes"
    )
    
    # TAK Server Configuration
    tak_server_url: str = Field(
        default="tcp://localhost:8087",
        description="TAK server URL (tcp://host:port or tls://host:port)"
    )
    tak_reconnect_interval: int = Field(
        default=5,
        ge=1,
        le=300,
        description="Seconds between TAK reconnection attempts"
    )
    tak_send_timeout: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="Timeout for sending CoT to TAK server"
    )
    
    # TLS Configuration (optional)
    tak_cert_file: Optional[str] = Field(
        default=None,
        description="Path to client certificate file for TLS"
    )
    tak_key_file: Optional[str] = Field(
        default=None,
        description="Path to client key file for TLS"
    )
    tak_ca_file: Optional[str] = Field(
        default=None,
        description="Path to CA certificate file for TLS"
    )
    
    # CoT Configuration
    device_type: str = Field(
        default="a-f-G-U-C",
        description="CoT type for devices (default: friendly ground unit)"
    )
    stale_time_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Time in seconds before CoT data becomes stale"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Optional log file path"
    )
    
    # Metrics Configuration
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    metrics_port: int = Field(
        default=8089,
        ge=1,
        le=65535,
        description="Port for Prometheus metrics endpoint"
    )
    
    # Performance Configuration
    max_concurrent_messages: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum concurrent messages to process"
    )
    message_queue_size: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Size of internal message queue"
    )
    
    # Health Check Configuration
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds between health checks"
    )
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper
    
    @validator("tak_server_url")
    def validate_tak_server_url(cls, v):
        """Validate TAK server URL format."""
        if not (v.startswith("tcp://") or v.startswith("tls://") or v.startswith("udp://")):
            raise ValueError("TAK server URL must start with tcp://, tls://, or udp://")
        return v
    
    @validator("tak_cert_file", "tak_key_file", "tak_ca_file")
    def validate_tls_files(cls, v, values):
        """Validate TLS configuration consistency."""
        if v is not None:
            # If any TLS file is specified, ensure we're using TLS
            if "tak_server_url" in values and not values["tak_server_url"].startswith("tls://"):
                raise ValueError("TLS certificates specified but TAK URL doesn't use tls://")
        return v
    
    @property
    def is_tls_enabled(self) -> bool:
        """Check if TLS is enabled."""
        return self.tak_server_url.startswith("tls://")
    
    @property
    def tak_protocol(self) -> str:
        """Get TAK protocol (tcp, tls, or udp)."""
        return self.tak_server_url.split("://")[0]
    
    @property
    def tak_host(self) -> str:
        """Extract host from TAK server URL."""
        url_parts = self.tak_server_url.split("://")[1].split(":")
        return url_parts[0]
    
    @property
    def tak_port(self) -> int:
        """Extract port from TAK server URL."""
        url_parts = self.tak_server_url.split("://")[1].split(":")
        if len(url_parts) > 1:
            return int(url_parts[1])
        # Default ports
        if self.tak_protocol == "tls":
            return 8089
        return 8087
    
    def get_summary(self) -> dict:
        """Get configuration summary for logging."""
        return {
            "udp_listener": f"{self.udp_listen_host}:{self.udp_listen_port}",
            "tak_server": self.tak_server_url,
            "tls_enabled": self.is_tls_enabled,
            "device_type": self.device_type,
            "stale_time": self.stale_time_seconds,
            "log_level": self.log_level,
            "metrics": f"port {self.metrics_port}" if self.metrics_enabled else "disabled"
        }
