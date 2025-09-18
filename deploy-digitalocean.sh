#!/bin/bash
# All-in-one deployment script for GPGGA to CoT Relay on DigitalOcean
# This script includes all necessary files inline for easy deployment

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}GPGGA to CoT Relay - DigitalOcean Deployment${NC}"
echo "============================================="
echo ""

# Install Docker if needed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Installing docker-compose...${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create project directory
PROJECT_DIR="$HOME/gpgga-cot-relay"
echo -e "${GREEN}Creating project directory: $PROJECT_DIR${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Clean up any existing deployment
docker-compose down 2>/dev/null || true

echo -e "${GREEN}Creating project files...${NC}"

# Create .env file
cat > .env << 'EOF'
# GPGGA to CoT Relay Configuration
TAK_SERVER_URL=tcp://your-tak-server.com:8087
UDP_LISTEN_PORT=5005
LOG_LEVEL=INFO
METRICS_PORT=8089
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF

# Create requirements.txt
cat > requirements.txt << 'EOF'
# Core dependencies
pytak>=5.4.0
aiofiles>=23.2.1
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0

# Logging and monitoring
structlog>=24.1.0
prometheus-client>=0.19.0
EOF

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cotrelay

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=cotrelay:cotrelay . .

# Switch to non-root user
USER cotrelay

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('localhost', 8089)); s.close()"

# Run the application
CMD ["python", "-m", "gpgga_cot_relay"]
EOF

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
services:
  gpgga-cot-relay:
    build: .
    container_name: gpgga-cot-relay
    restart: unless-stopped
    
    # Environment variables
    environment:
      - UDP_LISTEN_HOST=0.0.0.0
      - UDP_LISTEN_PORT=5005
      - TAK_SERVER_URL=${TAK_SERVER_URL:-tcp://tak-server:8087}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - METRICS_PORT=8089
      - DEVICE_TYPE=${DEVICE_TYPE:-a-f-G-U-C}
      - STALE_TIME_SECONDS=${STALE_TIME_SECONDS:-300}
    
    # Port mappings
    ports:
      - "${UDP_LISTEN_PORT:-5005}:5005/udp"  # UDP listener port
      - "${METRICS_PORT:-8089}:8089"         # Prometheus metrics
    
    # Volume for persistent logs
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config:ro
    
    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.1'
          memory: 128M
    
    # Network configuration
    networks:
      - cot-network

networks:
  cot-network:
    driver: bridge
EOF

# Create the Python package directory
mkdir -p gpgga_cot_relay

# Now we need to get the Python source files
echo -e "${RED}IMPORTANT: You need to copy the Python source files!${NC}"
echo ""
echo "The deployment structure is ready, but you need to copy the Python modules."
echo ""
echo "From your LOCAL machine, run this command:"
echo -e "${YELLOW}scp -r /Users/rupen/Documents/STATavl\ CoT\ Relay/gpgga_cot_relay root@$(curl -s ifconfig.me):$PROJECT_DIR/${NC}"
echo ""
echo "This will copy all the Python source files to your server."
echo ""
echo "After copying the files, run these commands:"
echo -e "${GREEN}cd $PROJECT_DIR${NC}"
echo -e "${GREEN}docker-compose build${NC}"
echo -e "${GREEN}docker-compose up -d${NC}"
echo ""
echo "Alternatively, you can create a deployment archive on your local machine:"
echo -e "${YELLOW}cd /Users/rupen/Documents/STATavl\ CoT\ Relay${NC}"
echo -e "${YELLOW}tar czf deploy.tar.gz gpgga_cot_relay/ requirements.txt Dockerfile docker-compose.yml${NC}"
echo -e "${YELLOW}scp deploy.tar.gz root@your-server:~/${NC}"
echo ""
echo "Then on the server:"
echo -e "${YELLOW}cd ~/gpgga-cot-relay && tar xzf ~/deploy.tar.gz${NC}"

# Create a completion script
cat > complete-deployment.sh << 'EOF'
#!/bin/bash
# Run this after copying the Python files

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if Python files exist
if [[ ! -f gpgga_cot_relay/__init__.py ]]; then
    echo -e "${RED}Error: Python source files not found!${NC}"
    echo "Please copy the gpgga_cot_relay directory first."
    exit 1
fi

# Edit configuration
echo -e "${GREEN}Opening configuration file for editing...${NC}"
echo "Please set your TAK_SERVER_URL:"
sleep 2
${EDITOR:-nano} .env

# Build and deploy
echo -e "${GREEN}Building Docker image...${NC}"
docker-compose build

echo -e "${GREEN}Starting service...${NC}"
docker-compose up -d

# Show status
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
docker-compose ps
echo ""
echo "Test with: nc -u localhost 5005"
echo "View logs: docker-compose logs -f"
echo "Metrics: curl http://localhost:8089/metrics"
EOF

chmod +x complete-deployment.sh

echo ""
echo -e "${GREEN}Initial setup complete!${NC}"
echo "Configuration file created at: $PROJECT_DIR/.env"
echo "Please follow the instructions above to complete the deployment."
