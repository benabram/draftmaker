#!/bin/bash

# Script to manage GitHub Actions self-hosted runner
# Usage: ./manage-github-runner.sh [start|stop|status|install|uninstall|restart|logs]

RUNNER_DIR="/home/benbuntu/actions-runner"
SERVICE_NAME="actions.runner.draftmaker.DESKTOP-RURNGT7"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_runner_dir() {
    if [ ! -d "$RUNNER_DIR" ]; then
        print_error "Runner directory not found at $RUNNER_DIR"
        exit 1
    fi
}

case "$1" in
    install)
        check_runner_dir
        print_status "Installing GitHub Actions runner as systemd service..."
        cd "$RUNNER_DIR"
        
        # Check if already installed
        if sudo systemctl list-units --full -all | grep -Fq "$SERVICE_NAME.service"; then
            print_warning "Service already installed. Use 'restart' to restart it."
            exit 0
        fi
        
        # Install the service
        sudo ./svc.sh install
        
        # Enable auto-start
        sudo systemctl enable $SERVICE_NAME.service
        
        print_status "Service installed and enabled for auto-start"
        print_status "Starting the service..."
        sudo ./svc.sh start
        ;;
        
    uninstall)
        check_runner_dir
        print_status "Uninstalling GitHub Actions runner service..."
        cd "$RUNNER_DIR"
        
        # Stop the service first
        sudo ./svc.sh stop
        
        # Uninstall the service
        sudo ./svc.sh uninstall
        
        print_status "Service uninstalled"
        ;;
        
    start)
        check_runner_dir
        print_status "Starting GitHub Actions runner..."
        
        # Check if running as service
        if sudo systemctl is-active --quiet $SERVICE_NAME.service; then
            print_warning "Runner is already running as a service"
        else
            cd "$RUNNER_DIR"
            if [ -f ./svc.sh ]; then
                sudo ./svc.sh start
            else
                # Fallback to running directly
                nohup ./run.sh > runner.log 2>&1 &
                print_status "Runner started in background (PID: $!)"
            fi
        fi
        ;;
        
    stop)
        check_runner_dir
        print_status "Stopping GitHub Actions runner..."
        
        # Try to stop as service first
        if sudo systemctl is-active --quiet $SERVICE_NAME.service; then
            cd "$RUNNER_DIR"
            sudo ./svc.sh stop
        else
            # Try to kill the process
            pkill -f "Runner.Listener"
            print_status "Runner stopped"
        fi
        ;;
        
    restart)
        check_runner_dir
        print_status "Restarting GitHub Actions runner..."
        cd "$RUNNER_DIR"
        
        if [ -f ./svc.sh ]; then
            sudo ./svc.sh stop
            sleep 2
            sudo ./svc.sh start
        else
            pkill -f "Runner.Listener"
            sleep 2
            nohup ./run.sh > runner.log 2>&1 &
        fi
        print_status "Runner restarted"
        ;;
        
    status)
        check_runner_dir
        print_status "Checking GitHub Actions runner status..."
        
        # Check service status
        if sudo systemctl is-active --quiet $SERVICE_NAME.service; then
            echo -e "${GREEN}✓${NC} Runner is running as a systemd service"
            sudo systemctl status $SERVICE_NAME.service --no-pager | head -10
        else
            # Check if running as process
            if pgrep -f "Runner.Listener" > /dev/null; then
                echo -e "${GREEN}✓${NC} Runner is running as a process"
                ps aux | grep -E "Runner.Listener" | grep -v grep
            else
                echo -e "${RED}✗${NC} Runner is not running"
            fi
        fi
        
        # Check GitHub connection
        echo ""
        print_status "Runner configuration:"
        if [ -f "$RUNNER_DIR/.runner" ]; then
            echo "  Name: $(grep '"agentName"' $RUNNER_DIR/.runner | cut -d'"' -f4)"
            echo "  Repository: $(grep '"gitHubUrl"' $RUNNER_DIR/.runner | cut -d'"' -f4)"
        fi
        ;;
        
    logs)
        print_status "Showing runner logs..."
        
        # Try systemd logs first
        if sudo systemctl is-active --quiet $SERVICE_NAME.service; then
            sudo journalctl -u $SERVICE_NAME.service -f
        elif [ -f "$RUNNER_DIR/runner.log" ]; then
            tail -f "$RUNNER_DIR/runner.log"
        else
            print_error "No logs found"
        fi
        ;;
        
    *)
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  install    - Install runner as systemd service (auto-start on boot)"
        echo "  uninstall  - Remove systemd service"
        echo "  start      - Start the runner"
        echo "  stop       - Stop the runner"
        echo "  restart    - Restart the runner"
        echo "  status     - Check runner status"
        echo "  logs       - Show runner logs (live)"
        exit 1
        ;;
esac
