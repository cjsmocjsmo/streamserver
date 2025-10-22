#!/bin/bash

# Raspberry Pi 3B+ Motion Detection Docker Manager
# Optimized for ARM architecture with Debian package priority

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="motion-stream-pi3b"
CONTAINER_NAME="motion-detection-pi3b"
PROJECT_NAME="motion-detection"

echo -e "${BLUE}🍓 Raspberry Pi 3B+ Motion Detection Stream Docker Manager${NC}"
echo "=============================================================="

# Check if running on Raspberry Pi
check_raspberry_pi() {
    if [[ ! -f /proc/device-tree/model ]] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Warning: This appears not to be a Raspberry Pi${NC}"
        echo "This container is optimized for Raspberry Pi 3B+"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Detected Raspberry Pi hardware${NC}"
    fi
}

# Check Docker installation
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found. Please install Docker first:${NC}"
        echo "curl -fsSL https://get.docker.com -o get-docker.sh"
        echo "sudo sh get-docker.sh"
        echo "sudo usermod -aG docker \$USER"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${YELLOW}⚠️  docker-compose not found. Installing...${NC}"
        sudo apt-get update
        sudo apt-get install -y docker-compose
    fi
    
    echo -e "${GREEN}✅ Docker and docker-compose available${NC}"
}

# Prepare directories and permissions
prepare_environment() {
    echo -e "${BLUE}📁 Preparing environment...${NC}"
    
    # Create required directories
    mkdir -p recordings logs
    
    # Set proper permissions for camera access
    if [[ -e /dev/video0 ]]; then
        echo -e "${GREEN}✅ Camera device found: /dev/video0${NC}"
        # Add current user to video group if not already
        if ! groups $USER | grep -q '\bvideo\b'; then
            echo -e "${YELLOW}⚠️  Adding user to video group...${NC}"
            sudo usermod -a -G video $USER
            echo -e "${YELLOW}⚠️  You may need to log out and log back in for group changes to take effect${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  No camera device found at /dev/video0${NC}"
        echo "Please ensure your camera is connected and detected"
    fi
    
    # Check GPU memory split
    if [[ -f /boot/config.txt ]]; then
        if ! grep -q "gpu_mem" /boot/config.txt; then
            echo -e "${YELLOW}⚠️  Consider adding 'gpu_mem=128' to /boot/config.txt for better camera performance${NC}"
        fi
    fi
}

# Build Docker image
build_image() {
    echo -e "${BLUE}🔨 Building Docker image for Raspberry Pi 3B+...${NC}"
    echo "This may take several minutes on first build..."
    
    docker build -t $IMAGE_NAME . \
        --build-arg BUILDPLATFORM=linux/arm/v7 \
        --build-arg TARGETPLATFORM=linux/arm/v7
    
    echo -e "${GREEN}✅ Docker image built successfully!${NC}"
}

# Run with docker-compose
run_compose() {
    echo -e "${BLUE}🚀 Starting motion detection service...${NC}"
    
    prepare_environment
    
    # Start services
    docker-compose up -d
    
    echo -e "${GREEN}✅ Service started successfully!${NC}"
    echo ""
    show_status
    echo ""
    echo -e "${GREEN}🌐 Web interface: http://localhost:8000${NC}"
    echo -e "${GREEN}📁 Recordings: ./recordings/${NC}"
    echo -e "${GREEN}📝 Logs: ./logs/${NC}"
}

# Show service status
show_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"
    
    if docker-compose ps | grep -q "Up"; then
        docker-compose ps
        echo ""
        echo -e "${GREEN}✅ Service is running${NC}"
        
        # Show resource usage
        echo -e "${BLUE}💾 Resource Usage:${NC}"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" $CONTAINER_NAME 2>/dev/null || echo "Container not running"
    else
        echo -e "${YELLOW}⚠️  Service is not running${NC}"
    fi
}

# Show logs
show_logs() {
    echo -e "${BLUE}📝 Showing container logs...${NC}"
    docker-compose logs -f
}

# Stop services
stop_services() {
    echo -e "${BLUE}🛑 Stopping motion detection service...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ Service stopped${NC}"
}

# Cleanup (remove containers and images)
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    
    # Stop and remove containers
    docker-compose down --rmi all --volumes --remove-orphans 2>/dev/null || true
    
    # Remove image
    docker rmi $IMAGE_NAME 2>/dev/null || true
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Update and restart
update() {
    echo -e "${BLUE}🔄 Updating motion detection service...${NC}"
    
    stop_services
    cleanup
    build_image
    run_compose
    
    echo -e "${GREEN}✅ Update complete${NC}"
}

# Show system information
system_info() {
    echo -e "${BLUE}ℹ️  System Information:${NC}"
    echo "Hostname: $(hostname)"
    echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
    echo "Architecture: $(uname -m)"
    echo "Kernel: $(uname -r)"
    
    if [[ -f /proc/device-tree/model ]]; then
        echo "Hardware: $(cat /proc/device-tree/model)"
    fi
    
    echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
    echo "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
    echo "Docker Compose: $(docker-compose --version | cut -d' ' -f3 | tr -d ',')"
    
    # Check camera
    if [[ -e /dev/video0 ]]; then
        echo "Camera: Detected at /dev/video0"
    else
        echo "Camera: Not detected"
    fi
    
    # Check GPU memory
    if command -v vcgencmd &> /dev/null; then
        echo "GPU Memory: $(vcgencmd get_mem gpu | cut -d'=' -f2)"
    fi
}

# Main command processing
case "${1:-menu}" in
    "build")
        check_raspberry_pi
        check_docker
        build_image
        ;;
    "run"|"start")
        check_raspberry_pi
        check_docker
        build_image
        run_compose
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        run_compose
        ;;
    "update")
        check_raspberry_pi
        check_docker
        update
        ;;
    "cleanup")
        cleanup
        ;;
    "info")
        system_info
        ;;
    "help"|"menu"|*)
        echo ""
        echo -e "${GREEN}Available commands:${NC}"
        echo "  build     - Build Docker image for Pi 3B+"
        echo "  run       - Build and start the motion detection service"
        echo "  status    - Show service status and resource usage"
        echo "  logs      - Show real-time container logs"
        echo "  stop      - Stop the service"
        echo "  restart   - Restart the service"
        echo "  update    - Stop, rebuild, and restart service"
        echo "  cleanup   - Remove all containers and images"
        echo "  info      - Show system information"
        echo ""
        echo -e "${BLUE}Quick start:${NC} ./docker-pi3b.sh run"
        echo ""
        echo -e "${YELLOW}Note:${NC} This script is optimized for Raspberry Pi 3B+"
        echo "Features: Debian packages priority, GPU acceleration, camera support"
        ;;
esac