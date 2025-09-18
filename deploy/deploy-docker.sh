#!/bin/bash
# Docker deployment script for GPGGA to CoT Relay

set -e

# Configuration
APP_NAME="gpgga-cot-relay"
DOCKER_IMAGE="$APP_NAME:latest"
CONTAINER_NAME="$APP_NAME"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_error() {
    echo -e "${RED}[!]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        print_status "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_status "Installing docker-compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
}

# Create configuration
create_config() {
    print_status "Creating configuration..."
    
    if [[ ! -f .env ]]; then
        cat > .env << EOF
# GPGGA to CoT Relay Configuration
TAK_SERVER_URL=tcp://your-tak-server.com:8087
UDP_LISTEN_PORT=5005
LOG_LEVEL=INFO
METRICS_PORT=8089
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF
        print_warning "Created .env file - please edit with your TAK server details"
    fi
}

# Build Docker image
build_image() {
    print_status "Building Docker image..."
    docker build -t $DOCKER_IMAGE .
}

# Deploy with docker-compose
deploy_compose() {
    print_status "Deploying with docker-compose..."
    
    # Stop existing container if running
    docker-compose down 2>/dev/null || true
    
    # Start new deployment
    docker-compose up -d
    
    print_status "Deployment complete!"
    echo ""
    echo "Commands:"
    echo "  View logs:      docker-compose logs -f"
    echo "  Stop service:   docker-compose down"
    echo "  Restart:        docker-compose restart"
    echo "  View metrics:   curl http://localhost:8089/metrics"
    echo ""
}

# Deploy single container (no docker-compose)
deploy_single() {
    print_status "Deploying single container..."
    
    # Stop and remove existing container
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    
    # Run new container
    docker run -d \
        --name $CONTAINER_NAME \
        --restart unless-stopped \
        -p 5005:5005/udp \
        -p 8089:8089 \
        --env-file .env \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/config:/app/config:ro \
        $DOCKER_IMAGE
    
    print_status "Container deployed!"
    echo ""
    echo "Commands:"
    echo "  View logs:      docker logs -f $CONTAINER_NAME"
    echo "  Stop container: docker stop $CONTAINER_NAME"
    echo "  Start container: docker start $CONTAINER_NAME"
    echo "  View metrics:   curl http://localhost:8089/metrics"
    echo ""
}

# Quick start function
quick_start() {
    print_status "Quick start deployment..."
    
    # Create minimal docker-compose.yml if not exists
    if [[ ! -f docker-compose.yml ]]; then
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  gpgga-cot-relay:
    image: ghcr.io/yourusername/gpgga-cot-relay:latest
    container_name: gpgga-cot-relay
    restart: unless-stopped
    ports:
      - "5005:5005/udp"
      - "8089:8089"
    environment:
      - TAK_SERVER_URL=${TAK_SERVER_URL}
      - UDP_LISTEN_PORT=${UDP_LISTEN_PORT:-5005}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - METRICS_PORT=${METRICS_PORT:-8089}
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config:ro
EOF
    fi
    
    create_config
    docker-compose pull
    docker-compose up -d
}

# Main menu
show_menu() {
    echo ""
    echo "GPGGA to CoT Relay - Docker Deployment"
    echo "======================================"
    echo ""
    echo "1) Quick start (pull from registry)"
    echo "2) Build and deploy locally"
    echo "3) Deploy with docker-compose"
    echo "4) Deploy single container"
    echo "5) Stop all containers"
    echo "6) View logs"
    echo "7) Exit"
    echo ""
}

# Main function
main() {
    check_docker
    
    if [[ $# -eq 0 ]]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Select option: " choice
            
            case $choice in
                1)
                    quick_start
                    ;;
                2)
                    create_config
                    build_image
                    deploy_compose
                    ;;
                3)
                    create_config
                    deploy_compose
                    ;;
                4)
                    create_config
                    build_image
                    deploy_single
                    ;;
                5)
                    docker-compose down 2>/dev/null || docker stop $CONTAINER_NAME 2>/dev/null || true
                    print_status "Containers stopped"
                    ;;
                6)
                    docker-compose logs -f 2>/dev/null || docker logs -f $CONTAINER_NAME
                    ;;
                7)
                    exit 0
                    ;;
                *)
                    print_error "Invalid option"
                    ;;
            esac
            
            echo ""
            read -p "Press Enter to continue..."
        done
    else
        # Command line mode
        case $1 in
            quick)
                quick_start
                ;;
            build)
                create_config
                build_image
                deploy_compose
                ;;
            deploy)
                create_config
                deploy_compose
                ;;
            stop)
                docker-compose down 2>/dev/null || docker stop $CONTAINER_NAME 2>/dev/null || true
                ;;
            logs)
                docker-compose logs -f 2>/dev/null || docker logs -f $CONTAINER_NAME
                ;;
            *)
                echo "Usage: $0 [quick|build|deploy|stop|logs]"
                exit 1
                ;;
        esac
    fi
}

main "$@"
