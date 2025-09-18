#!/bin/bash
# Standalone deployment script for GPGGA to CoT Relay
# This script can be run independently on a server

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}GPGGA to CoT Relay - Standalone Deployment${NC}"
echo "=========================================="
echo ""

# Check if we need to download the project files
if [[ ! -f Dockerfile ]]; then
    echo -e "${YELLOW}Project files not found. Downloading...${NC}"
    
    # Create a temporary archive script
    echo -e "${RED}ERROR: Project files not found!${NC}"
    echo ""
    echo "Please use one of these methods to deploy:"
    echo ""
    echo "1. Copy all project files to this server:"
    echo "   From your local machine, run:"
    echo "   scp -r /path/to/gpgga-cot-relay/* root@$(hostname -I | awk '{print $1}'):$(pwd)/"
    echo ""
    echo "2. Or create a tar archive and transfer:"
    echo "   On your local machine:"
    echo "   cd /path/to/gpgga-cot-relay"
    echo "   tar czf gpgga-cot-relay.tar.gz ."
    echo "   scp gpgga-cot-relay.tar.gz root@your-server:~/"
    echo ""
    echo "   Then on this server:"
    echo "   tar xzf gpgga-cot-relay.tar.gz"
    echo "   ./deploy.sh"
    echo ""
    exit 1
fi

# Run the main deployment
./deploy.sh
