"""GPGGA sentence parser with device ID extraction."""

import re
from typing import Optional
from datetime import datetime, time
from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger(__name__)


class GPGGAData(BaseModel):
    """Parsed GPGGA data model."""
    
    timestamp: Optional[time] = Field(None, description="UTC time from GPS")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    fix_quality: int = Field(..., description="GPS fix quality (0-8)")
    num_satellites: int = Field(..., description="Number of satellites in use")
    hdop: float = Field(..., description="Horizontal dilution of precision")
    altitude: float = Field(..., description="Altitude above mean sea level in meters")
    geoid_separation: Optional[float] = Field(None, description="Geoid separation in meters")
    dgps_time: Optional[float] = Field(None, description="Time since last DGPS update")
    dgps_station_id: Optional[str] = Field(None, description="DGPS station ID")
    device_id: str = Field(..., description="Device identifier")
    
    @validator("fix_quality")
    def validate_fix_quality(cls, v):
        if not 0 <= v <= 8:
            raise ValueError(f"Fix quality must be between 0 and 8, got {v}")
        return v
    
    @validator("num_satellites")
    def validate_num_satellites(cls, v):
        if v < 0:
            raise ValueError(f"Number of satellites cannot be negative, got {v}")
        return v
    
    @property
    def has_valid_fix(self) -> bool:
        """Check if GPS has a valid fix."""
        return self.fix_quality > 0
    
    @property
    def fix_quality_description(self) -> str:
        """Get human-readable fix quality description."""
        descriptions = {
            0: "Invalid",
            1: "GPS fix",
            2: "DGPS fix",
            3: "PPS fix",
            4: "Real Time Kinematic",
            5: "Float RTK",
            6: "Estimated",
            7: "Manual input",
            8: "Simulation"
        }
        return descriptions.get(self.fix_quality, "Unknown")


class GPGGAParser:
    """Parser for NMEA GPGGA sentences with custom device ID support."""
    
    # GPGGA sentence pattern with device ID before checksum
    GPGGA_PATTERN = re.compile(
        r'^\$GPGGA,'
        r'(\d{6}(?:\.\d+)?)?,'          # Time (HHMMSS.sss)
        r'(\d+\.\d+),'                   # Latitude (DDMM.mmmm or DDDMM.mmmm)
        r'([NS]),'                       # Latitude direction
        r'(\d+\.\d+),'                   # Longitude (DDDMM.mmmm or DDMM.mmmm)
        r'([EW]),'                       # Longitude direction
        r'([0-8]),'                      # Fix quality
        r'(\d+),'                        # Number of satellites
        r'(\d+\.\d+)?,'                  # HDOP
        r'(-?\d+\.?\d*),'                # Altitude
        r'M,'                            # Altitude units (always M)
        r'(-?\d+\.?\d*)?,'               # Geoid separation
        r'M?,'                           # Geoid units
        r'(\d+\.?\d*)?,'                 # DGPS time
        r'(\d+)?,'                       # DGPS station ID
        r'([^*]+)'                       # Device ID (custom field)
        r'\*([0-9A-F]{2})$'              # Checksum
    )
    
    @classmethod
    def parse(cls, sentence: str) -> Optional[GPGGAData]:
        """
        Parse a GPGGA sentence with device ID.
        
        Args:
            sentence: Raw GPGGA sentence string
            
        Returns:
            Parsed GPGGAData or None if parsing fails
        """
        try:
            # Strip whitespace and validate basic format
            sentence = sentence.strip()
            
            # Verify checksum
            if not cls._verify_checksum(sentence):
                logger.warning("Invalid GPGGA checksum", sentence=sentence)
                return None
            
            # Match the pattern
            match = cls.GPGGA_PATTERN.match(sentence)
            if not match:
                logger.warning("Invalid GPGGA format", sentence=sentence)
                return None
            
            # Extract groups
            (time_str, lat_str, lat_dir, lon_str, lon_dir, fix_quality,
             num_sats, hdop, altitude, geoid_sep, dgps_time, dgps_station,
             device_id, checksum) = match.groups()
            
            # Parse time
            timestamp = None
            if time_str:
                try:
                    hours = int(time_str[0:2])
                    minutes = int(time_str[2:4])
                    seconds = int(time_str[4:6])
                    microseconds = 0
                    if '.' in time_str:
                        frac = float('0.' + time_str.split('.')[1])
                        microseconds = int(frac * 1000000)
                    timestamp = time(hours, minutes, seconds, microseconds)
                except ValueError:
                    logger.warning("Invalid time format", time_str=time_str)
            
            # Parse coordinates
            latitude = cls._parse_coordinate(lat_str, lat_dir in 'S')
            longitude = cls._parse_coordinate(lon_str, lon_dir in 'W')
            
            # Create data object
            return GPGGAData(
                timestamp=timestamp,
                latitude=latitude,
                longitude=longitude,
                fix_quality=int(fix_quality),
                num_satellites=int(num_sats),
                hdop=float(hdop) if hdop else 0.0,
                altitude=float(altitude),
                geoid_separation=float(geoid_sep) if geoid_sep else None,
                dgps_time=float(dgps_time) if dgps_time else None,
                dgps_station_id=dgps_station if dgps_station else None,
                device_id=device_id.strip()
            )
            
        except Exception as e:
            logger.error("Failed to parse GPGGA sentence", 
                        sentence=sentence, 
                        error=str(e))
            return None
    
    @staticmethod
    def _verify_checksum(sentence: str) -> bool:
        """Verify NMEA checksum."""
        if '*' not in sentence:
            return False
        
        try:
            data, checksum = sentence.split('*')
            # Remove the $ if present
            if data.startswith('$'):
                data = data[1:]
            
            # Calculate checksum
            calculated = 0
            for char in data:
                calculated ^= ord(char)
            
            return f"{calculated:02X}" == checksum.upper()
        except Exception:
            return False
    
    @staticmethod
    def _parse_coordinate(coord_str: str, is_negative: bool) -> float:
        """
        Parse NMEA coordinate format to decimal degrees.
        
        Args:
            coord_str: Coordinate string in DDMM.mmmm or DDDMM.mmmm format
            is_negative: True if South or West
            
        Returns:
            Decimal degrees
        """
        # Split on decimal point to get the integer part
        parts = coord_str.split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else '0'
        
        # Last 2 digits of integer part are minutes
        if len(integer_part) >= 2:
            degrees = int(integer_part[:-2]) if len(integer_part) > 2 else 0
            minutes_int = int(integer_part[-2:])
            minutes = float(f"{minutes_int}.{decimal_part}")
        else:
            degrees = 0
            minutes = float(coord_str)
        
        decimal = degrees + (minutes / 60.0)
        return -decimal if is_negative else decimal
