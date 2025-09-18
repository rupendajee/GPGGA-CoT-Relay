"""Main entry point for GPGGA to CoT relay."""

import asyncio
import signal
import sys
from typing import Optional, Set
import time
import structlog
from prometheus_client import start_http_server

from .config import Settings
from .logging_config import (
    setup_logging, error_handler,
    MESSAGES_RECEIVED, MESSAGES_PARSED, COT_CONVERSIONS,
    COT_SENT, MESSAGE_PROCESSING_TIME, ACTIVE_DEVICES,
    TAK_CONNECTION_STATUS
)
from .gpgga_parser import GPGGAData
from .cot_converter import CoTConverter
from .udp_listener import UDPListener
from .tak_client import TAKClient

logger = structlog.get_logger(__name__)


class GPGGACoTRelay:
    """Main application class for GPGGA to CoT relay."""
    
    def __init__(self):
        """Initialize the relay application."""
        self.settings = Settings()
        self.cot_converter = CoTConverter(self.settings)
        self.udp_listener: Optional[UDPListener] = None
        self.tak_client: Optional[TAKClient] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.active_devices: Set[str] = set()
        self.last_device_cleanup = time.time()
        
    async def start(self) -> None:
        """Start the relay application."""
        logger.info("Starting GPGGA to CoT Relay",
                   config=self.settings.get_summary())
        
        # Initialize TAK client
        self.tak_client = TAKClient(self.settings)
        await self.tak_client.start()
        
        # Initialize UDP listener
        self.udp_listener = UDPListener(
            self.settings,
            self.handle_gpgga_message
        )
        await self.udp_listener.start()
        
        self._running = True
        
        # Start background tasks
        asyncio.create_task(self._monitor_health())
        asyncio.create_task(self._cleanup_devices())
        
        logger.info("GPGGA to CoT Relay started successfully")
    
    async def stop(self) -> None:
        """Stop the relay application gracefully."""
        logger.info("Stopping GPGGA to CoT Relay...")
        
        self._running = False
        self._shutdown_event.set()
        
        # Stop UDP listener
        if self.udp_listener:
            await self.udp_listener.stop()
        
        # Stop TAK client
        if self.tak_client:
            await self.tak_client.stop()
        
        logger.info("GPGGA to CoT Relay stopped")
    
    async def handle_gpgga_message(self, gpgga_data: GPGGAData, sender: tuple) -> None:
        """
        Handle a parsed GPGGA message.
        
        Args:
            gpgga_data: Parsed GPGGA data
            sender: Sender address (host, port)
        """
        start_time = time.time()
        
        try:
            # Update metrics
            MESSAGES_RECEIVED.inc()
            MESSAGES_PARSED.inc()
            
            # Track active device
            self.active_devices.add(gpgga_data.device_id)
            
            logger.info("Processing GPGGA message",
                       device_id=gpgga_data.device_id,
                       lat=gpgga_data.latitude,
                       lon=gpgga_data.longitude,
                       alt=gpgga_data.altitude,
                       fix_quality=gpgga_data.fix_quality_description,
                       satellites=gpgga_data.num_satellites,
                       sender=sender)
            
            # Convert to CoT
            cot_xml = self.cot_converter.convert(gpgga_data)
            
            if not cot_xml:
                error_handler.handle_conversion_error(
                    gpgga_data.device_id,
                    Exception("Failed to convert to CoT")
                )
                return
            
            COT_CONVERSIONS.inc()
            
            # Send to TAK
            if self.tak_client and self.tak_client.is_connected():
                success = await self.tak_client.send_cot(cot_xml)
                
                if success:
                    COT_SENT.inc()
                    logger.debug("CoT sent successfully",
                               device_id=gpgga_data.device_id)
                else:
                    error_handler.handle_send_error(
                        gpgga_data.device_id,
                        Exception("Failed to queue CoT message")
                    )
            else:
                logger.warning("TAK client not connected - message dropped",
                             device_id=gpgga_data.device_id)
            
            # Record processing time
            processing_time = time.time() - start_time
            MESSAGE_PROCESSING_TIME.observe(processing_time)
            
        except Exception as e:
            logger.error("Error processing GPGGA message",
                        device_id=gpgga_data.device_id,
                        error=str(e),
                        sender=sender)
            error_handler.handle_conversion_error(gpgga_data.device_id, e)
    
    async def _monitor_health(self) -> None:
        """Monitor application health and update metrics."""
        while self._running:
            try:
                # Update connection status
                if self.tak_client:
                    TAK_CONNECTION_STATUS.set(
                        1 if self.tak_client.is_connected() else 0
                    )
                
                # Update active devices count
                ACTIVE_DEVICES.set(len(self.active_devices))
                
                # Log statistics
                if self.udp_listener and self.tak_client:
                    stats = {
                        'udp': self.udp_listener.get_stats(),
                        'tak': self.tak_client.get_stats(),
                        'errors': error_handler.get_error_stats(),
                        'active_devices': len(self.active_devices)
                    }
                    
                    logger.info("Application statistics", **stats)
                
                # Wait for next check
                await asyncio.sleep(self.settings.health_check_interval)
                
            except Exception as e:
                logger.error("Error in health monitor", error=str(e))
                await asyncio.sleep(10)
    
    async def _cleanup_devices(self) -> None:
        """Periodically clean up inactive devices."""
        while self._running:
            try:
                # Clear device list every hour
                await asyncio.sleep(3600)
                
                old_count = len(self.active_devices)
                self.active_devices.clear()
                
                logger.info("Cleared active device list",
                          old_count=old_count)
                
            except Exception as e:
                logger.error("Error in device cleanup", error=str(e))
    
    async def run(self) -> None:
        """Run the application until shutdown."""
        await self.start()
        
        # Wait for shutdown signal
        await self._shutdown_event.wait()
        
        await self.stop()


def setup_signal_handlers(app: GPGGACoTRelay) -> None:
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal", signal=sig)
        asyncio.create_task(app.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    # Load settings
    settings = Settings()
    
    # Set up logging
    setup_logging(settings)
    
    # Start metrics server
    if settings.metrics_enabled:
        start_http_server(settings.metrics_port)
        logger.info("Prometheus metrics server started",
                   port=settings.metrics_port)
    
    # Create and run application
    app = GPGGACoTRelay()
    
    # Set up signal handlers
    setup_signal_handlers(app)
    
    try:
        await app.run()
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
