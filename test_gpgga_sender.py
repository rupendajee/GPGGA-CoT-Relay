#!/usr/bin/env python3
"""
Test script to send GPGGA messages to the relay for testing.
"""

import socket
import time
import random
import argparse
from datetime import datetime


def calculate_checksum(sentence):
    """Calculate NMEA checksum."""
    # Remove $ if present
    if sentence.startswith('$'):
        sentence = sentence[1:]
    
    checksum = 0
    for char in sentence:
        checksum ^= ord(char)
    
    return f"{checksum:02X}"


def generate_gpgga(device_id, lat=None, lon=None, alt=None):
    """Generate a valid GPGGA sentence with device ID."""
    # Current time
    now = datetime.utcnow()
    time_str = now.strftime("%H%M%S.00")
    
    # Random or specified position
    if lat is None:
        lat = random.uniform(25.0, 49.0)  # Continental US latitude range
    if lon is None:
        lon = random.uniform(-125.0, -66.0)  # Continental US longitude range
    if alt is None:
        alt = random.uniform(0, 2000)
    
    # Convert to NMEA format
    lat_deg = int(abs(lat))
    lat_min = (abs(lat) - lat_deg) * 60
    lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
    lat_dir = 'N' if lat >= 0 else 'S'
    
    lon_deg = int(abs(lon))
    lon_min = (abs(lon) - lon_deg) * 60
    lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
    lon_dir = 'E' if lon >= 0 else 'W'
    
    # Build sentence without checksum
    sentence = (
        f"GPGGA,{time_str},{lat_str},{lat_dir},{lon_str},{lon_dir},"
        f"1,08,0.9,{alt:.1f},M,46.9,M,,{device_id}"
    )
    
    # Calculate checksum
    checksum = calculate_checksum(sentence)
    
    # Complete sentence
    return f"${sentence}*{checksum}"


def send_gpgga(host, port, device_id, count=1, interval=1.0, 
               lat=None, lon=None, alt=None, movement=False):
    """Send GPGGA messages to the relay."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"Sending {count} GPGGA messages to {host}:{port}")
    print(f"Device ID: {device_id}")
    print(f"Interval: {interval}s")
    if movement:
        print("Movement simulation: ENABLED")
    print()
    
    # Initial position
    current_lat = lat if lat else random.uniform(30.0, 45.0)
    current_lon = lon if lon else random.uniform(-120.0, -75.0)
    current_alt = alt if alt else random.uniform(100, 500)
    
    for i in range(count):
        # Generate movement if enabled
        if movement and i > 0:
            # Small random movement
            current_lat += random.uniform(-0.001, 0.001)  # ~111 meters
            current_lon += random.uniform(-0.001, 0.001)  # ~111 meters at equator
            current_alt += random.uniform(-10, 10)  # altitude change
        
        # Generate and send GPGGA
        gpgga = generate_gpgga(
            device_id, 
            current_lat if movement or lat else None,
            current_lon if movement or lon else None,
            current_alt if movement or alt else None
        )
        
        sock.sendto(gpgga.encode(), (host, port))
        
        print(f"[{i+1}/{count}] Sent: {gpgga}")
        
        if i < count - 1:
            time.sleep(interval)
    
    sock.close()
    print("\nDone!")


def main():
    parser = argparse.ArgumentParser(
        description='Send test GPGGA messages to the CoT relay'
    )
    
    parser.add_argument(
        '-H', '--host',
        default='localhost',
        help='Target host (default: localhost)'
    )
    
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=5005,
        help='Target UDP port (default: 5005)'
    )
    
    parser.add_argument(
        '-d', '--device-id',
        default='TEST001',
        help='Device ID to include in GPGGA (default: TEST001)'
    )
    
    parser.add_argument(
        '-c', '--count',
        type=int,
        default=1,
        help='Number of messages to send (default: 1)'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=1.0,
        help='Interval between messages in seconds (default: 1.0)'
    )
    
    parser.add_argument(
        '--lat',
        type=float,
        help='Fixed latitude (default: random)'
    )
    
    parser.add_argument(
        '--lon',
        type=float,
        help='Fixed longitude (default: random)'
    )
    
    parser.add_argument(
        '--alt',
        type=float,
        help='Fixed altitude in meters (default: random)'
    )
    
    parser.add_argument(
        '-m', '--movement',
        action='store_true',
        help='Simulate device movement'
    )
    
    parser.add_argument(
        '--multi-device',
        type=int,
        help='Simulate multiple devices (creates TEST001, TEST002, etc.)'
    )
    
    args = parser.parse_args()
    
    if args.multi_device:
        # Simulate multiple devices
        for i in range(args.multi_device):
            device_id = f"TEST{i+1:03d}"
            print(f"\n=== Simulating device {device_id} ===")
            send_gpgga(
                args.host, args.port, device_id, 
                args.count, args.interval,
                args.lat, args.lon, args.alt,
                args.movement
            )
            if i < args.multi_device - 1:
                time.sleep(0.5)  # Brief pause between devices
    else:
        # Single device
        send_gpgga(
            args.host, args.port, args.device_id,
            args.count, args.interval,
            args.lat, args.lon, args.alt,
            args.movement
        )


if __name__ == '__main__':
    main()
