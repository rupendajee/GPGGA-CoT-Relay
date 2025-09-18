# DigitalOcean Deployment Guide for GPGGA to CoT Relay

This guide provides step-by-step instructions for deploying the GPGGA to CoT Relay on DigitalOcean.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create a Droplet](#create-a-droplet)
3. [Initial Server Setup](#initial-server-setup)
4. [Deploy with Docker](#deploy-with-docker)
5. [Deploy with Systemd](#deploy-with-systemd)
6. [Configure Firewall](#configure-firewall)
7. [Set Up Monitoring](#set-up-monitoring)
8. [Enable Automatic Updates](#enable-automatic-updates)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

- DigitalOcean account
- Domain name (optional, for TLS)
- TAK server URL and credentials
- Basic knowledge of Linux command line

## Create a Droplet

### 1. Log into DigitalOcean

Navigate to [cloud.digitalocean.com](https://cloud.digitalocean.com) and log in.

### 2. Create New Droplet

Click **"Create"** → **"Droplets"**

### 3. Choose Configuration

**Choose an image:**
- **Recommended**: Ubuntu 22.04 LTS

**Choose a plan:**
- **Minimum**: Basic → Regular → $6/month (1 vCPU, 1GB RAM)
- **Recommended**: Basic → Regular → $12/month (1 vCPU, 2GB RAM)
- **High Traffic**: Basic → Premium Intel → $24/month (2 vCPU, 4GB RAM)

**Choose datacenter:**
- Select closest to your TAK server or users

**Authentication:**
- **Recommended**: SSH keys (more secure)
- **Alternative**: Password

**Additional options:**
- ✅ Enable backups ($1.20/month for $6 droplet)
- ✅ Enable monitoring

**Finalize:**
- Hostname: `gpgga-cot-relay`
- Tags: `cot`, `tak`, `gps`

### 4. Create Droplet

Click **"Create Droplet"** and wait for provisioning (~55 seconds)

## Initial Server Setup

### 1. Connect to Your Droplet

```bash
ssh root@your_droplet_ip
```

### 2. Update System

```bash
apt update && apt upgrade -y
```

### 3. Create Swap Space (for small droplets)

```bash
# Create 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab

# Optimize swap usage
sysctl vm.swappiness=10
echo 'vm.swappiness=10' | tee -a /etc/sysctl.conf
```

### 4. Set Timezone

```bash
timedatectl set-timezone America/New_York  # Change to your timezone
```

## Deploy with Docker

### Option A: Quick Docker Deployment

```bash
# Download deployment script
wget https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/deploy/deploy-docker.sh
chmod +x deploy-docker.sh

# Run quick deployment
./deploy-docker.sh quick
```

### Option B: Manual Docker Deployment

#### 1. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

#### 2. Create Application Directory

```bash
mkdir -p /opt/gpgga-cot-relay
cd /opt/gpgga-cot-relay
```

#### 3. Download Files

```bash
# Download docker-compose.yml
wget https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/docker-compose.yml

# Create environment file
cat > .env << EOF
# TAK Server Configuration
TAK_SERVER_URL=tcp://your-tak-server.com:8087

# UDP Listener Configuration  
UDP_LISTEN_PORT=5005

# Logging Configuration
LOG_LEVEL=INFO

# Metrics Configuration
METRICS_PORT=8089

# CoT Configuration
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF
```

#### 4. Edit Configuration

```bash
nano .env
# Update TAK_SERVER_URL with your actual TAK server
```

#### 5. Deploy

```bash
# Start the service
docker-compose up -d

# Verify it's running
docker-compose ps
docker-compose logs
```

## Deploy with Systemd

### Option A: Automated Installation

```bash
# Download and run installer
wget https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/deploy/install.sh
chmod +x install.sh
sudo ./install.sh
```

### Option B: Manual Installation

#### 1. Install Python

```bash
apt install -y python3 python3-pip python3-venv git
```

#### 2. Create User and Directories

```bash
# Create system user
useradd --system --shell /bin/false --home-dir /opt/gpgga-cot-relay cotrelay

# Create directories
mkdir -p /opt/gpgga-cot-relay
mkdir -p /etc/gpgga-cot-relay
mkdir -p /var/log/gpgga-cot-relay
```

#### 3. Clone Repository

```bash
cd /opt/gpgga-cot-relay
git clone https://github.com/yourusername/gpgga-cot-relay.git .
```

#### 4. Install Application

```bash
# Create virtual environment
python3 -m venv venv

# Install dependencies
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -e .

# Set ownership
chown -R cotrelay:cotrelay /opt/gpgga-cot-relay
chown -R cotrelay:cotrelay /var/log/gpgga-cot-relay
```

#### 5. Configure

```bash
# Create configuration
cat > /etc/gpgga-cot-relay/config.env << EOF
TAK_SERVER_URL=tcp://your-tak-server.com:8087
UDP_LISTEN_PORT=5005
LOG_LEVEL=INFO
LOG_FILE=/var/log/gpgga-cot-relay/app.log
METRICS_PORT=8089
EOF

# Edit configuration
nano /etc/gpgga-cot-relay/config.env
```

#### 6. Install Service

```bash
# Copy service file
cp deploy/gpgga-cot-relay.service /etc/systemd/system/

# Reload and enable
systemctl daemon-reload
systemctl enable gpgga-cot-relay
systemctl start gpgga-cot-relay

# Check status
systemctl status gpgga-cot-relay
```

## Configure Firewall

### 1. Configure UFW (Ubuntu Firewall)

```bash
# Enable UFW
ufw --force enable

# Allow SSH (important!)
ufw allow 22/tcp

# Allow GPGGA UDP listener
ufw allow 5005/udp comment "GPGGA UDP listener"

# Allow Prometheus metrics (optional, only if needed externally)
ufw allow 8089/tcp comment "Prometheus metrics"

# Check status
ufw status
```

### 2. DigitalOcean Cloud Firewall (Recommended)

1. Go to **Networking** → **Firewalls** in DigitalOcean panel
2. Click **Create Firewall**
3. Name: `gpgga-cot-relay-fw`
4. Inbound Rules:
   - SSH: Port 22, Sources: Your IP
   - Custom UDP: Port 5005, Sources: GPS device IPs or 0.0.0.0/0
   - Custom TCP: Port 8089, Sources: Monitoring server IP
5. Apply to: Select your droplet

## Set Up Monitoring

### 1. Enable DigitalOcean Monitoring

```bash
# Install monitoring agent
curl -sSL https://repos.insights.digitalocean.com/install.sh | sudo bash
```

### 2. Configure Alerts

In DigitalOcean panel:
1. Go to **Monitoring** → **Alerts**
2. Create alerts for:
   - CPU usage > 80%
   - Memory usage > 90%
   - Disk usage > 85%

### 3. External Monitoring (Optional)

#### Prometheus + Grafana

```bash
# Create monitoring stack
cat > monitoring-compose.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=changeme

volumes:
  prometheus_data:
  grafana_data:
EOF

# Create Prometheus config
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'gpgga-cot-relay'
    static_configs:
      - targets: ['gpgga-cot-relay:8089']
EOF

# Start monitoring
docker-compose -f monitoring-compose.yml up -d
```

## Enable Automatic Updates

### 1. Security Updates

```bash
# Install unattended-upgrades
apt install -y unattended-upgrades

# Enable automatic security updates
dpkg-reconfigure --priority=low unattended-upgrades
```

### 2. Application Updates (Docker)

```bash
# Create update script
cat > /usr/local/bin/update-gpgga-relay.sh << 'EOF'
#!/bin/bash
cd /opt/gpgga-cot-relay
docker-compose pull
docker-compose up -d
docker image prune -f
EOF

chmod +x /usr/local/bin/update-gpgga-relay.sh

# Add to crontab (weekly updates)
(crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/local/bin/update-gpgga-relay.sh") | crontab -
```

## Backup and Recovery

### 1. Enable DigitalOcean Backups

This is done during droplet creation or:
1. Go to droplet page
2. Click **Backups**
3. Click **Enable Backups**

### 2. Manual Backup Script

```bash
# Create backup script
cat > /usr/local/bin/backup-gpgga-relay.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/gpgga-relay"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /etc/gpgga-cot-relay /opt/gpgga-cot-relay/.env

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/gpgga-cot-relay

# Keep only last 7 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-gpgga-relay.sh

# Add to daily cron
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-gpgga-relay.sh") | crontab -
```

### 3. Restore Procedure

```bash
# Restore configuration
tar -xzf /backups/gpgga-relay/config_20240115_020000.tar.gz -C /

# Restart service
docker-compose restart
# or
systemctl restart gpgga-cot-relay
```

## Troubleshooting

### 1. Check Service Status

```bash
# Docker
docker-compose ps
docker-compose logs -f

# Systemd
systemctl status gpgga-cot-relay
journalctl -u gpgga-cot-relay -f
```

### 2. Test UDP Connectivity

```bash
# Install netcat
apt install -y netcat

# Test UDP port
nc -u -l 5005  # On server
echo "test" | nc -u your_droplet_ip 5005  # From client
```

### 3. Check TAK Connection

```bash
# Test TAK server connectivity
telnet your-tak-server.com 8087

# Check logs for connection errors
docker-compose logs | grep -i "tak\|connection"
```

### 4. Performance Issues

```bash
# Check resource usage
htop
docker stats

# Check metrics
curl http://localhost:8089/metrics

# Increase droplet size if needed
# In DigitalOcean panel: Droplet → Resize
```

### 5. Common Issues

**UDP Port Not Accessible:**
- Check firewall rules
- Verify security groups
- Test from different network

**TAK Connection Fails:**
- Verify TAK server URL format
- Check network connectivity
- Validate certificates (for TLS)

**High Memory Usage:**
- Check for memory leaks in logs
- Adjust Docker memory limits
- Add swap space

**Parse Errors:**
- Enable DEBUG logging
- Verify GPGGA format
- Check device ID placement

## Maintenance

### Weekly Tasks

- Review logs for errors
- Check disk usage
- Verify backups

### Monthly Tasks

- Update system packages
- Review metrics/performance
- Test recovery procedure

### Quarterly Tasks

- Review and update firewall rules
- Audit user access
- Update documentation

## Cost Optimization

### Estimated Monthly Costs

- Basic Droplet (1GB): $6
- With backups: +$1.20
- Monitoring: Free
- **Total**: ~$7.20/month

### Cost Saving Tips

1. Use smallest droplet that meets needs
2. Enable backups only if critical
3. Use block storage for logs (cheaper)
4. Consider reserved instances for long-term

## Support

For issues specific to:
- **DigitalOcean**: support.digitalocean.com
- **Application**: github.com/yourusername/gpgga-cot-relay/issues
- **TAK Server**: Refer to TAK documentation
