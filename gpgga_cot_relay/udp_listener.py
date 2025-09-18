"""Asynchronous UDP listener for GPGGA messages."""

import asyncio
import socket
from typing import Optional, Callable, Awaitable
import structlog

from .config import Settings
from .gpgga_parser import GPGGAParser, GPGGAData

logger = structlog.get_logger(__name__)


class UDPProtocol(asyncio.DatagramProtocol):
    """Asyncio UDP protocol handler."""
    
    def __init__(self, message_handler: Callable[[GPGGAData, tuple], Awaitable[None]]):
        """
        Initialize UDP protocol.
        
        Args:
            message_handler: Async function to handle parsed GPGGA data
        """
        self.message_handler = message_handler
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.messages_received = 0
        self.parse_errors = 0
        
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Called when connection is established."""
        self.transport = transport
        sock = transport.get_extra_info('socket')
        if sock:
            # Set socket options for better performance
            try:
                # Increase receive buffer size
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
                # Enable address reuse
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception as e:
                logger.warning("Failed to set socket options", error=str(e))
        
        logger.info("UDP listener started", 
                   local_addr=transport.get_extra_info('sockname'))
    
    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """
        Handle received datagram.
        
        Args:
            data: Raw datagram data
            addr: Sender address (host, port)
        """
        self.messages_received += 1
        
        try:
            # Decode the data
            message = data.decode('utf-8').strip()
            
            logger.debug("Received UDP message",
                        sender=addr,
                        message=message,
                        bytes=len(data))
            
            # Parse GPGGA sentence
            gpgga_data = GPGGAParser.parse(message)
            
            if gpgga_data:
                # Schedule the message handler
                asyncio.create_task(self._handle_message(gpgga_data, addr))
            else:
                self.parse_errors += 1
                logger.warning("Failed to parse GPGGA message",
                             sender=addr,
                             message=message)
                
        except UnicodeDecodeError as e:
            self.parse_errors += 1
            logger.error("Failed to decode UDP message",
                        sender=addr,
                        error=str(e),
                        data_hex=data.hex())
        except Exception as e:
            self.parse_errors += 1
            logger.error("Unexpected error processing UDP message",
                        sender=addr,
                        error=str(e))
    
    async def _handle_message(self, gpgga_data: GPGGAData, addr: tuple) -> None:
        """
        Handle parsed GPGGA message.
        
        Args:
            gpgga_data: Parsed GPGGA data
            addr: Sender address
        """
        try:
            await self.message_handler(gpgga_data, addr)
        except Exception as e:
            logger.error("Error in message handler",
                        device_id=gpgga_data.device_id,
                        sender=addr,
                        error=str(e))
    
    def error_received(self, exc: Exception) -> None:
        """Handle protocol errors."""
        logger.error("UDP protocol error", error=str(exc))
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.error("UDP connection lost", error=str(exc))
        else:
            logger.info("UDP connection closed")
    
    def get_stats(self) -> dict:
        """Get listener statistics."""
        return {
            "messages_received": self.messages_received,
            "parse_errors": self.parse_errors,
            "error_rate": self.parse_errors / max(1, self.messages_received)
        }


class UDPListener:
    """High-performance asynchronous UDP listener."""
    
    def __init__(self, settings: Settings, 
                 message_handler: Callable[[GPGGAData, tuple], Awaitable[None]]):
        """
        Initialize UDP listener.
        
        Args:
            settings: Application settings
            message_handler: Async function to handle parsed GPGGA data
        """
        self.settings = settings
        self.message_handler = message_handler
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[UDPProtocol] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the UDP listener."""
        if self._running:
            logger.warning("UDP listener already running")
            return
        
        try:
            # Create endpoint
            loop = asyncio.get_event_loop()
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self.message_handler),
                local_addr=(self.settings.udp_listen_host, self.settings.udp_listen_port),
                reuse_address=True,
                reuse_port=True  # Allow multiple processes to bind
            )
            
            self._running = True
            
            logger.info("UDP listener started successfully",
                       host=self.settings.udp_listen_host,
                       port=self.settings.udp_listen_port)
            
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error("UDP port already in use",
                           port=self.settings.udp_listen_port)
            elif e.errno == 13:  # Permission denied
                logger.error("Permission denied to bind UDP port",
                           port=self.settings.udp_listen_port,
                           hint="Try a port > 1024 or run as root")
            else:
                logger.error("Failed to start UDP listener",
                           error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error starting UDP listener",
                        error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the UDP listener."""
        if not self._running:
            return
        
        self._running = False
        
        if self.transport:
            self.transport.close()
            self.transport = None
        
        logger.info("UDP listener stopped")
    
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running
    
    def get_stats(self) -> dict:
        """Get listener statistics."""
        if self.protocol:
            return self.protocol.get_stats()
        return {
            "messages_received": 0,
            "parse_errors": 0,
            "error_rate": 0.0
        }
