#!/usr/bin/env python3
"""Send a test CoT message directly to TAK server."""

import socket
import sys
from datetime import datetime, timezone, timedelta

def send_test_cot(host, port):
    """Send a test CoT message directly."""
    
    # Create a simple CoT event
    now = datetime.now(timezone.utc)
    stale = now + timedelta(minutes=5)
    
    cot_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="TEST-DIRECT-001" type="a-f-G-U-C" time="{now.isoformat()}Z" start="{now.isoformat()}Z" stale="{stale.isoformat()}Z" how="m-g">
  <point lat="36.0" lon="-94.0" hae="100.0" ce="10.0" le="10.0"/>
  <detail>
    <contact callsign="DIRECT-TEST"/>
    <remarks>Direct CoT test from GPGGA relay</remarks>
  </detail>
</event>
'''
    
    print(f"Connecting to {host}:{port}...")
    
    try:
        # Connect to TAK server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        
        print("Connected! Sending CoT...")
        print(f"CoT XML:\n{cot_xml}")
        
        # Send the CoT
        sock.send(cot_xml.encode('utf-8'))
        
        print("CoT sent successfully!")
        
        # Keep connection open briefly
        import time
        time.sleep(2)
        
        sock.close()
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 2:
        host = sys.argv[1]
        port = int(sys.argv[2])
    else:
        host = "takserver.twistedkelp.com"
        port = 8087
    
    print(f"Sending test CoT to {host}:{port}")
    if send_test_cot(host, port):
        print("\nCheck your TAK client for a marker at 36°N, 94°W labeled 'DIRECT-TEST'")
    else:
        print("\nFailed to send CoT")
