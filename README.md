# GPGGA to CoT Relay

A lightweight, reliable relay service that converts GPGGA GPS messages to Cursor on Target (CoT) format for Team Awareness Kit (TAK) integration.

## Features

- **High Performance**: Asynchronous UDP listener built with asyncio
- **Reliable**: Automatic reconnection, comprehensive error handling, and health monitoring
- **Lightweight**: Minimal resource usage with configurable limits
- **Observable**: Prometheus metrics, structured logging, and health checks
- **Flexible Deployment**: Docker, systemd, or standalone Python
- **TAK Compatible**: Full CoT 2.0 support with proper type hierarchy
- **Device Tracking**: Automatic device ID extraction from GPGGA sentences

## Architecture

```
GPS Devices → UDP:5005 → GPGGA Parser → CoT Converter → TAK Server
                              ↓
                         Device Tracker
                              ↓
                     Prometheus Metrics
```

## GPGGA Format

The relay expects GPGGA sentences with a custom device ID field before the checksum:

```
$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,DEVICE001*47
```

Standard GPGGA fields plus:
- **DEVICE001**: Device identifier (added before checksum)

## Quick Start

### Option 1: Deploy from GitHub (Recommended for DigitalOcean)

On your DigitalOcean droplet, run this one-liner (replace `yourusername` with your GitHub username):

```bash
curl -sSL https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/quick-deploy.sh | sudo bash -s yourusername
```

Then edit the configuration:
```bash
nano /opt/gpgga-cot-relay/.env  # Set your TAK_SERVER_URL
cd /opt/gpgga-cot-relay && docker-compose restart
```

### Option 2: Local Docker Deployment

1. Clone the repository:
```bash
git clone https://github.com/yourusername/gpgga-cot-relay.git
cd gpgga-cot-relay
```

2. Configure your TAK server:
```bash
cp .env.example .env
# Edit .env with your TAK server URL
```

3. Deploy with Docker Compose:
```bash
docker-compose up -d
```

### Using Systemd

1. Run the installation script:
```bash
sudo ./deploy/install.sh
```

2. Configure the service:
```bash
sudo nano /etc/gpgga-cot-relay/config.env
# Set TAK_SERVER_URL
```

3. Start the service:
```bash
sudo systemctl start gpgga-cot-relay
sudo systemctl enable gpgga-cot-relay
```

## Configuration

Configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TAK_SERVER_URL` | `tcp://localhost:8087` | TAK server connection URL |
| `UDP_LISTEN_PORT` | `5005` | Port for GPGGA UDP listener |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `METRICS_PORT` | `8089` | Prometheus metrics port |
| `DEVICE_TYPE` | `a-f-G-U-C` | CoT type for devices |
| `STALE_TIME_SECONDS` | `300` | Time before CoT data becomes stale |

### TLS Configuration

For secure TAK connections:

```bash
TAK_SERVER_URL=tls://tak-server.com:8089
TAK_CERT_FILE=/path/to/client.pem
TAK_KEY_FILE=/path/to/client.key
TAK_CA_FILE=/path/to/ca.pem
```

## Monitoring

### Prometheus Metrics

Available at `http://localhost:8089/metrics`:

- `gpgga_messages_received_total` - Total GPGGA messages received
- `gpgga_messages_parsed_total` - Successfully parsed messages
- `gpgga_parse_errors_total` - Parse errors
- `cot_conversions_total` - Successful CoT conversions
- `cot_messages_sent_total` - CoT messages sent to TAK
- `active_devices_count` - Number of active devices
- `tak_connection_status` - TAK connection status (1=connected)

### Logging

Structured JSON logs with configurable output:

```bash
# View logs (Docker)
docker-compose logs -f

# View logs (systemd)
journalctl -u gpgga-cot-relay -f
```

### Health Checks

The service includes automatic health monitoring:
- UDP listener status
- TAK connection status
- Message processing statistics
- Error rates and types

## Performance Tuning

### Resource Limits

Configure in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 256M
```

### Message Queue

Adjust for your workload:
```bash
MAX_CONCURRENT_MESSAGES=100
MESSAGE_QUEUE_SIZE=1000
```

### UDP Buffer

For high-traffic environments:
```bash
UDP_BUFFER_SIZE=65536
```

## Testing

### Send Test GPGGA Message

```bash
# Using netcat
echo '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,TEST001*47' | nc -u localhost 5005

# Using Python
python3 -c "
import socket
msg = '\$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,TEST001*47'
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(msg.encode(), ('localhost', 5005))
"
```

### Verify Metrics

```bash
curl http://localhost:8089/metrics | grep gpgga
```

## Troubleshooting

### Connection Issues

1. Check TAK server URL format:
   - TCP: `tcp://server:8087`
   - TLS: `tls://server:8089`
   - UDP: `udp://server:4242`

2. Verify network connectivity:
```bash
telnet tak-server.com 8087
```

3. Check logs for errors:
```bash
docker-compose logs | grep ERROR
```

### Parse Errors

1. Verify GPGGA format including device ID
2. Check checksum calculation
3. Enable DEBUG logging to see raw messages

### Performance Issues

1. Monitor metrics endpoint
2. Check resource usage:
```bash
docker stats gpgga-cot-relay
```
3. Increase queue sizes if needed

## Development

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run tests
pytest

# Run with debug logging
LOG_LEVEL=DEBUG python -m gpgga_cot_relay
```

### Building Docker Image

```bash
docker build -t gpgga-cot-relay:latest .
```

## License

MIT License - see LICENSE file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Support

- Issues: https://github.com/yourusername/gpgga-cot-relay/issues
- Documentation: https://github.com/yourusername/gpgga-cot-relay/wiki
