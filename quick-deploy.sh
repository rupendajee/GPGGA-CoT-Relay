#!/bin/bash
# Quick deployment script - can be piped from curl
# Usage: curl -sSL https://raw.githubusercontent.com/yourusername/gpgga-cot-relay/main/quick-deploy.sh | sudo bash -s yourusername

set -e

# Get GitHub username from argument or use default
GITHUB_USER=${1:-yourusername}
# Try to detect the actual repo name by checking common variations
REPO_NAME="gpgga-cot-relay"
for name in "GPGGA-CoT-Relay" "gpgga-cot-relay" "GPGGACoTRelay"; do
    if curl -s -o /dev/null -w "%{http_code}" "https://github.com/$GITHUB_USER/$name" | grep -q "200"; then
        REPO_NAME=$name
        break
    fi
done
GITHUB_REPO="https://github.com/$GITHUB_USER/$REPO_NAME.git"

echo "Deploying GPGGA to CoT Relay from $GITHUB_REPO"

# Create a temporary script and execute it
cat > /tmp/deploy-gpgga-relay.sh << 'SCRIPT'
#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

GITHUB_REPO="__GITHUB_REPO__"
INSTALL_DIR="/opt/gpgga-cot-relay"

echo -e "${GREEN}GPGGA to CoT Relay - Quick Deploy${NC}"
echo "================================="

# Install git if needed
if ! command -v git &> /dev/null; then
    apt-get update && apt-get install -y git curl
fi

# Install Docker
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
fi

# Install docker-compose
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Clone repository
echo -e "${GREEN}Cloning repository...${NC}"
rm -rf $INSTALL_DIR
git clone $GITHUB_REPO $INSTALL_DIR
cd $INSTALL_DIR

# Create default .env
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || cat > .env << EOF
TAK_SERVER_URL=tcp://your-tak-server.com:8087
UDP_LISTEN_PORT=5005
LOG_LEVEL=INFO
METRICS_PORT=8089
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF
fi

# Build and deploy
echo -e "${GREEN}Building and deploying...${NC}"
docker-compose build
docker-compose up -d

# Configure firewall
ufw allow 5005/udp 2>/dev/null || true
ufw allow 8089/tcp 2>/dev/null || true

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo -e "${RED}IMPORTANT: Edit TAK server configuration:${NC}"
echo "nano $INSTALL_DIR/.env"
echo ""
echo "Then restart:"
echo "cd $INSTALL_DIR && docker-compose restart"
echo ""
echo "View logs: cd $INSTALL_DIR && docker-compose logs -f"
SCRIPT

# Replace the GitHub repo placeholder
sed -i "s|__GITHUB_REPO__|$GITHUB_REPO|g" /tmp/deploy-gpgga-relay.sh

# Make executable and run
chmod +x /tmp/deploy-gpgga-relay.sh
/tmp/deploy-gpgga-relay.sh

# Clean up
rm -f /tmp/deploy-gpgga-relay.sh
