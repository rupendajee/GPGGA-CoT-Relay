"""Cursor on Target (CoT) converter for GPGGA data."""

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import structlog

from .gpgga_parser import GPGGAData
from .config import Settings

logger = structlog.get_logger(__name__)


class CoTConverter:
    """Convert GPGGA data to Cursor on Target (CoT) format."""
    
    def __init__(self, settings: Settings):
        """
        Initialize the CoT converter.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.device_uids: Dict[str, str] = {}  # Cache device IDs to UIDs
        
    def convert(self, gpgga_data: GPGGAData) -> Optional[str]:
        """
        Convert GPGGA data to CoT XML format.
        
        Args:
            gpgga_data: Parsed GPGGA data
            
        Returns:
            CoT XML string or None if conversion fails
        """
        try:
            # Get or create UID for device
            uid = self._get_device_uid(gpgga_data.device_id)
            
            # Create current timestamp
            now = datetime.now(timezone.utc)
            time_str = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            # Calculate stale time
            stale_time = now + timedelta(seconds=self.settings.stale_time_seconds)
            stale_str = stale_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            # Create CoT event element
            event = ET.Element("event")
            event.set("version", "2.0")
            event.set("uid", uid)
            event.set("type", self.settings.device_type)
            event.set("time", time_str)
            event.set("start", time_str)
            event.set("stale", stale_str)
            event.set("how", self._get_how_attribute(gpgga_data))
            
            # Add point element
            point = ET.SubElement(event, "point")
            point.set("lat", str(gpgga_data.latitude))
            point.set("lon", str(gpgga_data.longitude))
            point.set("hae", str(gpgga_data.altitude))  # Height above ellipsoid
            
            # Set circular error based on fix quality and HDOP
            ce = self._calculate_circular_error(gpgga_data)
            point.set("ce", str(ce))
            point.set("le", str(ce))  # Linear error same as circular for GPS
            
            # Add detail element
            detail = ET.SubElement(event, "detail")
            
            # Add contact information
            contact = ET.SubElement(detail, "contact")
            contact.set("callsign", gpgga_data.device_id)
            
            # Add precision location information
            precisionlocation = ET.SubElement(detail, "precisionlocation")
            precisionlocation.set("altsrc", "GPS")
            precisionlocation.set("geopointsrc", "GPS")
            
            # Add track information if we have valid GPS data
            if gpgga_data.has_valid_fix:
                track = ET.SubElement(detail, "track")
                track.set("course", "0.0")  # We don't have course from GPGGA
                track.set("speed", "0.0")   # We don't have speed from GPGGA
                
            # Add GPS status information
            gps_status = ET.SubElement(detail, "__gps")
            gps_status.set("numSats", str(gpgga_data.num_satellites))
            gps_status.set("hdop", str(gpgga_data.hdop))
            gps_status.set("fixQuality", str(gpgga_data.fix_quality))
            gps_status.set("fixQualityDesc", gpgga_data.fix_quality_description)
            
            # Add device info
            device_info = ET.SubElement(detail, "__device")
            device_info.set("uid", gpgga_data.device_id)
            device_info.set("type", "GPS Tracker")
            
            # Add remarks with additional info
            remarks = ET.SubElement(detail, "remarks")
            remarks_text = f"GPGGA Device: {gpgga_data.device_id}"
            if gpgga_data.timestamp:
                remarks_text += f", GPS Time: {gpgga_data.timestamp.isoformat()}"
            remarks.text = remarks_text
            
            # Convert to XML string
            xml_str = ET.tostring(event, encoding='unicode', method='xml')
            
            logger.debug("Converted GPGGA to CoT",
                        device_id=gpgga_data.device_id,
                        uid=uid,
                        lat=gpgga_data.latitude,
                        lon=gpgga_data.longitude,
                        alt=gpgga_data.altitude)
            
            return xml_str
            
        except Exception as e:
            logger.error("Failed to convert GPGGA to CoT",
                        device_id=gpgga_data.device_id,
                        error=str(e))
            return None
    
    def _get_device_uid(self, device_id: str) -> str:
        """
        Get or create a persistent UID for a device.
        
        Args:
            device_id: Device identifier from GPGGA
            
        Returns:
            CoT UID for the device
        """
        if device_id not in self.device_uids:
            # Create a deterministic UUID based on device ID
            namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # URL namespace
            device_uuid = uuid.uuid5(namespace, f"gpgga-device-{device_id}")
            self.device_uids[device_id] = f"GPGGA-{device_uuid}"
            logger.info("Created new UID for device",
                       device_id=device_id,
                       uid=self.device_uids[device_id])
        
        return self.device_uids[device_id]
    
    def _get_how_attribute(self, gpgga_data: GPGGAData) -> str:
        """
        Determine the 'how' attribute based on GPS fix quality.
        
        Args:
            gpgga_data: Parsed GPGGA data
            
        Returns:
            CoT 'how' attribute value
        """
        # Map fix quality to CoT 'how' attribute
        how_mapping = {
            0: "h-g-i-g-o",  # Invalid - no GPS
            1: "h-gps",       # Standard GPS
            2: "h-dgps",      # Differential GPS
            3: "h-pps",       # PPS fix
            4: "h-rtk",       # RTK
            5: "h-rtk",       # Float RTK
            6: "h-e",         # Estimated
            7: "h-m",         # Manual
            8: "h-s"          # Simulation
        }
        
        return how_mapping.get(gpgga_data.fix_quality, "h-gps")
    
    def _calculate_circular_error(self, gpgga_data: GPGGAData) -> float:
        """
        Calculate circular error based on HDOP and fix quality.
        
        Args:
            gpgga_data: Parsed GPGGA data
            
        Returns:
            Circular error in meters
        """
        # Base error estimates for different fix qualities (meters)
        base_errors = {
            0: 9999.0,  # Invalid
            1: 5.0,     # GPS
            2: 2.0,     # DGPS
            3: 1.0,     # PPS
            4: 0.1,     # RTK
            5: 0.5,     # Float RTK
            6: 10.0,    # Estimated
            7: 50.0,    # Manual
            8: 100.0    # Simulation
        }
        
        base_error = base_errors.get(gpgga_data.fix_quality, 10.0)
        
        # Apply HDOP factor (typically HDOP * 5m for standard GPS)
        if gpgga_data.hdop > 0:
            return min(base_error * gpgga_data.hdop, 9999.0)
        else:
            return base_error
