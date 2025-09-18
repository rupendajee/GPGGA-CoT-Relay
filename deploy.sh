#!/bin/bash
# Simple deployment script for GPGGA to CoT Relay

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}GPGGA to CoT Relay - Deployment${NC}"
echo "================================"
echo ""

# Check if running as root (recommended for DigitalOcean)
if [[ $EUID -eq 0 ]]; then
   echo -e "${GREEN}Running as root${NC}"
else
   echo -e "${YELLOW}Not running as root. Some operations may require sudo.${NC}"
fi

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo -e "${GREEN}Docker installed successfully${NC}"
fi

# Install docker-compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}docker-compose not found. Installing...${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}docker-compose installed successfully${NC}"
fi

# Create .env file if it doesn't exist
if [[ ! -f .env ]]; then
    echo -e "${YELLOW}Creating .env configuration file...${NC}"
    cat > .env << EOF
# GPGGA to CoT Relay Configuration
TAK_SERVER_URL=tcp://your-tak-server.com:8087
UDP_LISTEN_PORT=5005
LOG_LEVEL=INFO
METRICS_PORT=8089
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF
    echo -e "${RED}IMPORTANT: Edit .env file and set your TAK_SERVER_URL${NC}"
    echo ""
    read -p "Press Enter to edit .env file now, or Ctrl+C to exit and edit manually..."
    ${EDITOR:-nano} .env
fi

# Build and start the service
echo ""
echo -e "${GREEN}Building Docker image...${NC}"
docker build -t gpgga-cot-relay:latest .

echo ""
echo -e "${GREEN}Starting service...${NC}"
docker-compose up -d

# Show status
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
docker-compose ps
echo ""
echo "Service Information:"
echo "===================="
echo "UDP Listener: 0.0.0.0:5005"
echo "Metrics:      http://localhost:8089/metrics"
echo ""
echo "Useful Commands:"
echo "================"
echo "View logs:         docker-compose logs -f"
echo "Stop service:      docker-compose down"
echo "Restart service:   docker-compose restart"
echo "Check status:      docker-compose ps"
echo ""
echo "Test GPGGA sender: python3 test_gpgga_sender.py"
echo ""

# Quick health check
echo -e "${GREEN}Checking service health...${NC}"
sleep 3
if curl -s http://localhost:8089/metrics > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Metrics endpoint is responding${NC}"
else
    echo -e "${YELLOW}⚠ Metrics endpoint not yet available (service may still be starting)${NC}"
fi

echo ""
echo -e "${GREEN}Setup complete! The relay is now listening for GPGGA messages on UDP port 5005.${NC}"
