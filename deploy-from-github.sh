#!/bin/bash
# Deploy GPGGA to CoT Relay from GitHub
# This script can be run directly on the DigitalOcean droplet

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
GITHUB_REPO="https://github.com/yourusername/gpgga-cot-relay.git"
INSTALL_DIR="/opt/gpgga-cot-relay"
BRANCH="main"

echo -e "${GREEN}GPGGA to CoT Relay - GitHub Deployment${NC}"
echo "======================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
apt-get update
apt-get install -y git curl

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo -e "${GREEN}Docker installed successfully${NC}"
fi

# Install docker-compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Installing docker-compose...${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}docker-compose installed successfully${NC}"
fi

# Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${GREEN}Updating existing repository...${NC}"
    cd $INSTALL_DIR
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo -e "${GREEN}Cloning repository...${NC}"
    rm -rf $INSTALL_DIR
    git clone $GITHUB_REPO $INSTALL_DIR
    cd $INSTALL_DIR
    git checkout $BRANCH
fi

# Create .env file if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo -e "${YELLOW}Creating .env configuration file...${NC}"
    cat > $INSTALL_DIR/.env << EOF
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
    ${EDITOR:-nano} $INSTALL_DIR/.env
fi

# Stop existing deployment
echo -e "${GREEN}Stopping existing deployment...${NC}"
cd $INSTALL_DIR
docker-compose down 2>/dev/null || true

# Build and start the service
echo -e "${GREEN}Building Docker image...${NC}"
docker-compose build

echo -e "${GREEN}Starting service...${NC}"
docker-compose up -d

# Configure firewall
if command -v ufw &> /dev/null; then
    echo -e "${GREEN}Configuring firewall...${NC}"
    ufw allow 5005/udp comment "GPGGA UDP listener" || true
    ufw allow 8089/tcp comment "Prometheus metrics" || true
fi

# Show status
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
docker-compose ps
echo ""
echo "Service Information:"
echo "===================="
echo "Installation directory: $INSTALL_DIR"
echo "UDP Listener: 0.0.0.0:5005"
echo "Metrics: http://localhost:8089/metrics"
echo ""
echo "Useful Commands:"
echo "================"
echo "View logs:         cd $INSTALL_DIR && docker-compose logs -f"
echo "Stop service:      cd $INSTALL_DIR && docker-compose down"
echo "Restart service:   cd $INSTALL_DIR && docker-compose restart"
echo "Update from Git:   $0"
echo "Test GPGGA:        cd $INSTALL_DIR && python3 test_gpgga_sender.py"
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
echo -e "${GREEN}Setup complete!${NC}"
