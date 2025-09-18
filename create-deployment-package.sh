#!/bin/bash
# Create a deployment package for easy transfer to DigitalOcean

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Creating deployment package...${NC}"

# Create deployment directory
DEPLOY_DIR="deployment-package"
rm -rf $DEPLOY_DIR
mkdir -p $DEPLOY_DIR

# Copy essential files
echo "Copying files..."
cp -r gpgga_cot_relay $DEPLOY_DIR/
cp requirements.txt $DEPLOY_DIR/
cp Dockerfile $DEPLOY_DIR/
cp docker-compose.yml $DEPLOY_DIR/
cp deploy.sh $DEPLOY_DIR/
cp test_gpgga_sender.py $DEPLOY_DIR/

# Create README for deployment
cat > $DEPLOY_DIR/README_DEPLOYMENT.txt << 'EOF'
GPGGA to CoT Relay - Deployment Instructions
===========================================

1. Edit the configuration:
   nano .env
   (Set your TAK_SERVER_URL)

2. Deploy the service:
   ./deploy.sh

3. Test the deployment:
   python3 test_gpgga_sender.py

4. View logs:
   docker-compose logs -f

5. Check metrics:
   curl http://localhost:8089/metrics
EOF

# Create the package
echo -e "${GREEN}Creating deployment package...${NC}"
tar czf gpgga-cot-relay-deploy.tar.gz $DEPLOY_DIR/

# Clean up
rm -rf $DEPLOY_DIR

echo -e "${GREEN}Deployment package created: gpgga-cot-relay-deploy.tar.gz${NC}"
echo ""
echo "To deploy on your DigitalOcean droplet:"
echo ""
echo "1. Copy the package to your server:"
echo -e "   ${YELLOW}scp gpgga-cot-relay-deploy.tar.gz root@your-server-ip:~/${NC}"
echo ""
echo "2. SSH into your server and extract:"
echo -e "   ${YELLOW}ssh root@your-server-ip${NC}"
echo -e "   ${YELLOW}tar xzf gpgga-cot-relay-deploy.tar.gz${NC}"
echo -e "   ${YELLOW}cd deployment-package${NC}"
echo -e "   ${YELLOW}./deploy.sh${NC}"
echo ""
