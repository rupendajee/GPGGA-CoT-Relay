#!/bin/bash
# GPGGA to CoT Relay Installation Script
# Supports Ubuntu/Debian and RHEL/CentOS systems

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="gpgga-cot-relay"
APP_USER="cotrelay"
APP_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
LOG_DIR="/var/log/$APP_NAME"
DATA_DIR="/var/lib/$APP_NAME"
SYSTEMD_DIR="/etc/systemd/system"

# Functions
print_status() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_error() {
    echo -e "${RED}[!]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/debian_version ]]; then
        OS="debian"
        PACKAGE_MANAGER="apt-get"
    elif [[ -f /etc/redhat-release ]]; then
        OS="redhat"
        PACKAGE_MANAGER="yum"
    else
        print_error "Unsupported operating system"
        exit 1
    fi
    print_status "Detected $OS-based system"
}

install_dependencies() {
    print_status "Installing system dependencies..."
    
    if [[ $OS == "debian" ]]; then
        apt-get update
        apt-get install -y python3 python3-pip python3-venv git curl
    else
        yum install -y python3 python3-pip git curl
    fi
    
    # Install Docker if requested
    if [[ "$1" == "--with-docker" ]]; then
        print_status "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        
        # Install docker-compose
        print_status "Installing docker-compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
}

create_user() {
    print_status "Creating application user..."
    
    if id "$APP_USER" &>/dev/null; then
        print_warning "User $APP_USER already exists"
    else
        useradd --system --shell /bin/false --home-dir $APP_DIR $APP_USER
        print_status "Created user $APP_USER"
    fi
}

create_directories() {
    print_status "Creating application directories..."
    
    mkdir -p $APP_DIR
    mkdir -p $CONFIG_DIR
    mkdir -p $LOG_DIR
    mkdir -p $DATA_DIR
    
    chown -R $APP_USER:$APP_USER $APP_DIR
    chown -R $APP_USER:$APP_USER $LOG_DIR
    chown -R $APP_USER:$APP_USER $DATA_DIR
    
    chmod 755 $APP_DIR
    chmod 755 $CONFIG_DIR
    chmod 755 $LOG_DIR
    chmod 755 $DATA_DIR
}

install_application() {
    print_status "Installing application..."
    
    # Check if running from git repo or need to download
    if [[ -f "setup.py" ]]; then
        print_status "Installing from current directory..."
        cp -r . $APP_DIR/
    else
        print_status "Cloning from repository..."
        git clone https://github.com/yourusername/$APP_NAME.git $APP_DIR
    fi
    
    cd $APP_DIR
    
    # Create virtual environment
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/pip install -e .
    
    # Create wrapper script
    cat > /usr/local/bin/$APP_NAME << EOF
#!/bin/bash
exec $APP_DIR/venv/bin/python -m gpgga_cot_relay "\$@"
EOF
    
    chmod +x /usr/local/bin/$APP_NAME
    chown -R $APP_USER:$APP_USER $APP_DIR
}

configure_application() {
    print_status "Configuring application..."
    
    # Create default configuration
    if [[ ! -f $CONFIG_DIR/config.env ]]; then
        cat > $CONFIG_DIR/config.env << EOF
# GPGGA to CoT Relay Configuration
# Edit this file to configure the application

# TAK Server Configuration
TAK_SERVER_URL=tcp://your-tak-server.com:8087

# UDP Listener Configuration
UDP_LISTEN_PORT=5005

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=$LOG_DIR/gpgga-cot-relay.log

# Metrics Configuration
METRICS_ENABLED=true
METRICS_PORT=8089

# CoT Configuration
DEVICE_TYPE=a-f-G-U-C
STALE_TIME_SECONDS=300
EOF
        print_warning "Created default configuration at $CONFIG_DIR/config.env"
        print_warning "Please edit this file to set your TAK server URL"
    fi
    
    chmod 640 $CONFIG_DIR/config.env
    chown root:$APP_USER $CONFIG_DIR/config.env
}

install_systemd_service() {
    print_status "Installing systemd service..."
    
    cp deploy/gpgga-cot-relay.service $SYSTEMD_DIR/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable $APP_NAME
    
    print_status "Systemd service installed and enabled"
}

configure_firewall() {
    print_status "Configuring firewall..."
    
    # Check if ufw is installed
    if command -v ufw &> /dev/null; then
        print_status "Configuring UFW firewall..."
        ufw allow 5005/udp comment "GPGGA UDP listener"
        ufw allow 8089/tcp comment "Prometheus metrics"
    
    # Check if firewalld is installed
    elif command -v firewall-cmd &> /dev/null; then
        print_status "Configuring firewalld..."
        firewall-cmd --permanent --add-port=5005/udp
        firewall-cmd --permanent --add-port=8089/tcp
        firewall-cmd --reload
    
    else
        print_warning "No supported firewall found. Please manually open ports:"
        print_warning "  - UDP 5005 (GPGGA listener)"
        print_warning "  - TCP 8089 (Prometheus metrics)"
    fi
}

setup_log_rotation() {
    print_status "Setting up log rotation..."
    
    cat > /etc/logrotate.d/$APP_NAME << EOF
$LOG_DIR/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $APP_USER $APP_USER
    sharedscripts
    postrotate
        systemctl reload $APP_NAME > /dev/null 2>&1 || true
    endscript
}
EOF
}

print_completion_message() {
    echo ""
    print_status "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Edit the configuration file: $CONFIG_DIR/config.env"
    echo "2. Set your TAK server URL and other settings"
    echo "3. Start the service: systemctl start $APP_NAME"
    echo "4. Check status: systemctl status $APP_NAME"
    echo "5. View logs: journalctl -u $APP_NAME -f"
    echo ""
    echo "The service will start automatically on boot."
    echo ""
    echo "Metrics are available at: http://localhost:8089/metrics"
    echo "UDP listener is on port: 5005"
    echo ""
}

# Main installation flow
main() {
    print_status "Starting GPGGA to CoT Relay installation..."
    
    check_root
    detect_os
    install_dependencies "$@"
    create_user
    create_directories
    install_application
    configure_application
    install_systemd_service
    configure_firewall
    setup_log_rotation
    
    print_completion_message
}

# Run main function with all arguments
main "$@"
