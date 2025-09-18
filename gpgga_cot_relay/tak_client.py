"""TAK client for sending CoT messages with connection management."""

import asyncio
import ssl
from typing import Optional, Union
from pathlib import Path
import structlog
import pytak

from .config import Settings

logger = structlog.get_logger(__name__)


class TAKClient:
    """Managed TAK client with automatic reconnection and error handling."""
    
    def __init__(self, settings: Settings):
        """
        Initialize TAK client.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.tx_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.message_queue_size)
        self.tx_worker: Optional[pytak.TXWorker] = None
        self._running = False
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self.messages_sent = 0
        self.send_errors = 0
        
    async def start(self) -> None:
        """Start the TAK client and connection manager."""
        if self._running:
            logger.warning("TAK client already running")
            return
        
        self._running = True
        
        # Start the connection manager
        self._reconnect_task = asyncio.create_task(self._connection_manager())
        
        logger.info("TAK client started",
                   server=self.settings.tak_server_url)
    
    async def stop(self) -> None:
        """Stop the TAK client gracefully."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel reconnection task
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        # Stop TX worker
        if self.tx_worker:
            await self._disconnect()
        
        # Clear the queue
        while not self.tx_queue.empty():
            try:
                self.tx_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        logger.info("TAK client stopped")
    
    async def send_cot(self, cot_xml: str) -> bool:
        """
        Send a CoT message to the TAK server.
        
        Args:
            cot_xml: CoT XML string to send
            
        Returns:
            True if queued successfully, False otherwise
        """
        if not self._running:
            logger.warning("Cannot send CoT - client not running")
            return False
        
        try:
            # Try to add to queue with timeout
            await asyncio.wait_for(
                self.tx_queue.put(cot_xml.encode('utf-8')),
                timeout=self.settings.tak_send_timeout
            )
            
            logger.debug("CoT message queued for transmission",
                        queue_size=self.tx_queue.qsize())
            
            return True
            
        except asyncio.TimeoutError:
            self.send_errors += 1
            logger.error("Timeout queuing CoT message - queue full",
                        queue_size=self.tx_queue.qsize())
            return False
        except Exception as e:
            self.send_errors += 1
            logger.error("Failed to queue CoT message",
                        error=str(e))
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
                
                # Monitor connection health
                await asyncio.sleep(self.settings.health_check_interval)
                
                # Check if worker is still running
                if self.tx_worker and self.tx_worker._reader_task:
                    if self.tx_worker._reader_task.done():
                        # Connection lost
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
        # Parse connection URL
        protocol = self.settings.tak_protocol
        host = self.settings.tak_host
        port = self.settings.tak_port
        
        # Create SSL context if needed
        ssl_context = None
        if protocol == "tls":
            ssl_context = self._create_ssl_context()
        
        # Create appropriate worker based on protocol
        if protocol == "tcp" or protocol == "tls":
            self.tx_worker = pytak.TCPTXWorker(
                tx_queue=self.tx_queue,
                host=host,
                port=port,
                ssl_context=ssl_context
            )
        elif protocol == "udp":
            self.tx_worker = pytak.UDPTXWorker(
                tx_queue=self.tx_queue,
                host=host,
                port=port
            )
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")
        
        # Start the worker
        await self.tx_worker.start()
        
        # Set up message counter
        self._setup_message_counter()
    
    async def _disconnect(self) -> None:
        """Disconnect from TAK server."""
        if self.tx_worker:
            try:
                await self.tx_worker.stop()
            except Exception as e:
                logger.error("Error stopping TX worker", error=str(e))
            finally:
                self.tx_worker = None
    
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
    
    def _setup_message_counter(self) -> None:
        """Set up message counting for statistics."""
        if hasattr(self.tx_worker, '_writer'):
            # Wrap the writer to count messages
            original_write = self.tx_worker._writer.write
            
            def counting_write(data):
                self.messages_sent += 1
                return original_write(data)
            
            self.tx_worker._writer.write = counting_write
    
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
            "queue_size": self.tx_queue.qsize() if self.tx_queue else 0,
            "queue_capacity": self.settings.message_queue_size
        }
