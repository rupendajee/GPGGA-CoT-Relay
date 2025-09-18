"""Simple TAK client for sending CoT messages."""

import asyncio
import socket
import ssl
from typing import Optional
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class SimpleTAKClient:
    """Simple TAK client with direct socket connection."""
    
    def __init__(self, settings: Settings):
        """Initialize TAK client."""
        self.settings = settings
        self.host = self.settings.tak_host
        self.port = self.settings.tak_port
        self.protocol = self.settings.tak_protocol
        
        self._running = False
        self._connected = False
        self._writer: Optional[asyncio.StreamWriter] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        self.messages_sent = 0
        self.send_errors = 0
        
    async def start(self) -> None:
        """Start the TAK client."""
        if self._running:
            logger.warning("TAK client already running")
            return
        
        self._running = True
        self._reconnect_task = asyncio.create_task(self._connection_manager())
        
        logger.info("TAK client started", server=self.settings.tak_server_url)
    
    async def stop(self) -> None:
        """Stop the TAK client."""
        if not self._running:
            return
        
        self._running = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        await self._disconnect()
        
        logger.info("TAK client stopped")
    
    async def send_cot(self, cot_xml: str) -> bool:
        """Send a CoT message to the TAK server."""
        if not self._running or not self._connected:
            logger.warning("Cannot send CoT - client not connected")
            return False
        
        try:
            # Ensure XML ends with newline for TAK server
            if not cot_xml.endswith('\n'):
                cot_xml += '\n'
            
            # Send the CoT message
            self._writer.write(cot_xml.encode('utf-8'))
            await self._writer.drain()
            
            self.messages_sent += 1
            logger.debug("CoT message sent successfully", 
                        message_count=self.messages_sent)
            
            return True
            
        except Exception as e:
            self.send_errors += 1
            logger.error("Failed to send CoT message", error=str(e))
            self._connected = False
            return False
    
    async def _connection_manager(self) -> None:
        """Manage TAK server connection with automatic reconnection."""
        while self._running:
            try:
                if not self._connected:
                    logger.info("Attempting to connect to TAK server",
                               server=self.settings.tak_server_url)
                    
                    await self._connect()
                    self._connected = True
                    
                    logger.info("Connected to TAK server successfully",
                               server=self.settings.tak_server_url)
                
                # Keep connection alive
                await asyncio.sleep(self.settings.health_check_interval)
                
                # Simple connection check - try to write empty data
                if self._writer:
                    try:
                        self._writer.write(b'')
                        await self._writer.drain()
                    except:
                        logger.warning("TAK connection lost - reconnecting")
                        self._connected = False
                        await self._disconnect()
                
            except Exception as e:
                logger.error("TAK connection error",
                           error=str(e),
                           server=self.settings.tak_server_url)
                self._connected = False
                
                # Wait before reconnecting
                await asyncio.sleep(self.settings.tak_reconnect_interval)
    
    async def _connect(self) -> None:
        """Establish connection to TAK server."""
        # Create SSL context if needed
        ssl_context = None
        if self.protocol == "tls":
            ssl_context = self._create_ssl_context()
        
        # Connect based on protocol
        if self.protocol in ["tcp", "tls"]:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, 
                self.port,
                ssl=ssl_context
            )
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
    
    async def _disconnect(self) -> None:
        """Disconnect from TAK server."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as e:
                logger.error("Error closing connection", error=str(e))
            finally:
                self._writer = None
                self._reader = None
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS connections."""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Load certificates if provided
        if self.settings.tak_cert_file and self.settings.tak_key_file:
            try:
                context.load_cert_chain(
                    certfile=self.settings.tak_cert_file,
                    keyfile=self.settings.tak_key_file
                )
                logger.info("Loaded client certificates for TLS")
            except Exception as e:
                logger.error("Failed to load client certificates",
                           cert_file=self.settings.tak_cert_file,
                           key_file=self.settings.tak_key_file,
                           error=str(e))
                raise
        
        # Load CA certificate if provided
        if self.settings.tak_ca_file:
            try:
                context.load_verify_locations(cafile=self.settings.tak_ca_file)
                logger.info("Loaded CA certificate for TLS")
            except Exception as e:
                logger.error("Failed to load CA certificate",
                           ca_file=self.settings.tak_ca_file,
                           error=str(e))
                raise
        else:
            # Disable certificate verification if no CA provided
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            logger.warning("TLS certificate verification disabled - no CA certificate provided")
        
        return context
    
    def is_connected(self) -> bool:
        """Check if connected to TAK server."""
        return self._connected
    
    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            "connected": self._connected,
            "messages_sent": self.messages_sent,
            "send_errors": self.send_errors,
            "error_rate": self.send_errors / max(1, self.messages_sent + self.send_errors),
            "queue_size": 0,  # No queue in simple implementation
            "queue_capacity": 0
        }
