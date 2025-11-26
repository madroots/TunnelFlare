#!/usr/bin/env bash

# ==============================================================================
# Cloudflare Tunnel Manager - Multi-Tunnel Edition
# Expose multiple local apps simultaneously to the internet via cloudflared
# ==============================================================================

# Ensure we're running under bash
if [ -z "$BASH_VERSION" ]; then
    echo "❌ This script requires bash. Do not run with sh."
    echo "✅ Run it like this: bash $0"
    exit 1
fi

set -euo pipefail

# Colors for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global config
TUNNELS_DIR="${HOME}/.cf-tunnels"
LOGS_DIR="${TUNNELS_DIR}/logs"
mkdir -p "$TUNNELS_DIR" "$LOGS_DIR" 2>/dev/null || true

DEFAULT_PORT=3000
DEFAULT_PROTOCOL="http"

# Check if cloudflared is installed
check_dependencies() {
    if ! command -v cloudflared &> /dev/null; then
        echo -e "${RED}❌ cloudflared is not installed.${NC}"
        echo -e "${YELLOW}Please install it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation${NC}"
        exit 1
    fi
}

# Display banner
show_banner() {
    clear
    echo -e "${PURPLE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║      Cloudflare Multi-Tunnel Manager v2.1          ║"
    echo "║  Expose multiple local apps to the internet        ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Generate a random tunnel name
generate_tunnel_name() {
    local prefix="${1:-app}"
    echo "${prefix}-$(openssl rand -hex 3 2>/dev/null || echo $(date +%s | sha256sum | head -c 6))"
}

# Get uptime in human-readable format
get_uptime() {
    local pid=$1
    if command -v ps &> /dev/null; then
        ps -o etime= -p "$pid" 2>/dev/null | sed 's/ //g' || echo "unknown"
    else
        echo "unknown"
    fi
}

# Check if tunnel is still running
is_tunnel_alive() {
    local pid_file="$1"
    [ -f "$pid_file" ] || return 1
    local pid=$(cat "$pid_file" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# List all running tunnels
list_running_tunnels() {
    echo -e "${BLUE}═════════════ ACTIVE TUNNELS ═════════════${NC}"
    
    local count=0
    
    # Use nullglob to handle empty directory gracefully
    shopt -s nullglob 2>/dev/null || true
    
    # Get list of .pid files
    local pid_files=("$TUNNELS_DIR"/*.pid)
    
    for pid_file in "${pid_files[@]}"; do
        # Skip if not a real file (shouldn't happen with nullglob, but be safe)
        if [[ ! -f "$pid_file" ]]; then
            continue
        fi
        
        local tunnel_id=$(basename "$pid_file" .pid)
        local config_file="$TUNNELS_DIR/$tunnel_id.config"
        local log_file="$LOGS_DIR/$tunnel_id.log"
        
        if ! is_tunnel_alive "$pid_file"; then
            # Clean up dead tunnel
            rm -f "$pid_file" "$config_file" 2>/dev/null
            continue
        fi
        
        count=$((count + 1))
        local pid=$(cat "$pid_file" 2>/dev/null)
        local uptime=$(get_uptime "$pid")
        
        # Read config
        local port="?"
        local protocol="?"
        local name="$tunnel_id"
        local url=""
        
        if [ -f "$config_file" ]; then
            while IFS= read -r line; do
                case $line in
                    PORT=*) port="${line#PORT=}" ;;
                    PROTOCOL=*) protocol="${line#PROTOCOL=}" ;;
                    NAME=*) name="${line#NAME=}" ;;
                esac
            done < "$config_file" 2>/dev/null
        fi
        
        # Extract public URL from log
        if [ -f "$log_file" ]; then
            url=$(grep -o "https://[a-zA-Z0-9-]*\.trycloudflare\.com" "$log_file" | tail -1 2>/dev/null)
        fi
        
        echo -e "${GREEN}[$count] ${CYAN}$name${NC}"
        echo -e "    ${YELLOW}PID:${NC} $pid ${YELLOW}Uptime:${NC} $uptime"
        echo -e "    ${YELLOW}Local:${NC} ${protocol}://localhost:${port}"
        if [ -n "$url" ]; then
            echo -e "    ${YELLOW}Public:${NC} ${CYAN}$url${NC}"
        else
            echo -e "    ${YELLOW}Public:${NC} ${RED}Initializing...${NC}"
        fi
        echo -e "${BLUE}────────────────────────────────────────${NC}"
    done
    
    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}No active tunnels running${NC}"
        echo -e "${BLUE}────────────────────────────────────────${NC}"
    fi
    
    echo ""
}

# Display menu
show_menu() {
    list_running_tunnels
    
    echo -e "${CYAN}══════════════════ MENU ══════════════════${NC}"
    echo -e "${GREEN}1. 🚀 Start new tunnel${NC}"
    echo -e "${GREEN}2. 🛑 Stop a specific tunnel${NC}"
    echo -e "${GREEN}3. 🛑 Stop ALL tunnels${NC}"
    echo -e "${GREEN}4. 📋 View logs for a tunnel${NC}"
    echo -e "${GREEN}5. ⚙️  Configure default settings${NC}"
    echo -e "${GREEN}6. ❓ Help & Tips${NC}"
    echo -e "${RED}0. 🚪 Exit${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Enter your choice:${NC} "
}

# Get user input with default fallback
get_input_with_default() {
    local prompt="$1"
    local default="$2"
    read -p "$(echo -e "${prompt} [${default}]: ")" input
    echo "${input:-$default}"
}

# Start tunnel
start_tunnel() {
    echo -e "${BLUE}🚀 Starting New Cloudflare Tunnel...${NC}"
    
    # Get tunnel name
    local suggested_name=$(generate_tunnel_name "app")
    local name=$(get_input_with_default "Tunnel name (for your reference)" "$suggested_name")
    
    # Sanitize name (alphanumeric + dashes/underscores only)
    name=$(echo "$name" | sed 's/[^a-zA-Z0-9_-]/_/g')
    if [ -z "$name" ]; then
        name="$suggested_name"
    fi
    
    # Check if name already exists and is running
    local tunnel_id="$name"
    local counter=1
    while [ -f "$TUNNELS_DIR/$tunnel_id.pid" ] && is_tunnel_alive "$TUNNELS_DIR/$tunnel_id.pid"; do
        tunnel_id="${name}_${counter}"
        counter=$((counter + 1))
    done
    
    # Get port and protocol
    local port=$(get_input_with_default "Enter local port" "$DEFAULT_PORT")
    local protocol=$(get_input_with_default "Protocol (http/https)" "$DEFAULT_PROTOCOL")
    
    # Validate port
    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        echo -e "${RED}❌ Invalid port number${NC}"
        return
    fi
    
    # Validate protocol
    if [[ "$protocol" != "http" && "$protocol" != "https" ]]; then
        echo -e "${RED}❌ Protocol must be 'http' or 'https'${NC}"
        return
    fi
    
    # Check if local service is running
    if ! nc -z localhost "$port" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  No service detected on localhost:$port${NC}"
        read -p "Continue anyway? (y/N): " confirm
        if [[ "${confirm,,}" != "y" ]]; then
            return
        fi
    fi
    
    # Create config file
    local config_file="$TUNNELS_DIR/$tunnel_id.config"
    local log_file="$LOGS_DIR/$tunnel_id.log"
    local pid_file="$TUNNELS_DIR/$tunnel_id.pid"
    
    {
        echo "NAME=$name"
        echo "PORT=$port"
        echo "PROTOCOL=$protocol"
        echo "START_TIME=$(date)"
    } > "$config_file"
    
    # Start tunnel in background
    local url="${protocol}://localhost:${port}"
    
    echo -e "${GREEN}📡 Exposing $url as '$tunnel_id'...${NC}"
    echo -e "${YELLOW}This may take a moment. Please wait...${NC}"
    
    cloudflared tunnel --url "$url" > "$log_file" 2>&1 &
    local tunnel_pid=$!
    
    # Save PID
    echo "$tunnel_pid" > "$pid_file"
    
    # Wait a moment for tunnel to initialize
    sleep 3
    
    # Check if started successfully
    if kill -0 "$tunnel_pid" 2>/dev/null; then
        echo -e "${GREEN}✅ Tunnel '$tunnel_id' started successfully!${NC}"
        echo -e "${CYAN}PID: $tunnel_pid${NC}"
        
        # Try to extract and display the public URL
        sleep 2
        if grep -q "trycloudflare.com" "$log_file" 2>/dev/null; then
            public_url=$(grep -o "https://[a-zA-Z0-9-]*\.trycloudflare\.com" "$log_file" | head -1 2>/dev/null)
            if [ -n "$public_url" ]; then
                echo -e "${GREEN}🌐 Your public URL: ${CYAN}$public_url${NC}"
                echo -e "${YELLOW}Note: This URL is temporary and will change on restart${NC}"
            fi
        fi
        
        echo -e "${BLUE}📝 Logs: $log_file${NC}"
    else
        echo -e "${RED}❌ Failed to start tunnel${NC}"
        if [ -f "$log_file" ]; then
            echo -e "${YELLOW}Last few lines from log:${NC}"
            tail -5 "$log_file"
        fi
        rm -f "$pid_file" "$config_file" 2>/dev/null
    fi
}

# Get tunnel selection from user
select_tunnel() {
    local action="$1"
    local tunnels=()
    local count=0
    
    # Use nullglob to handle empty directory
    shopt -s nullglob 2>/dev/null || true
    local pid_files=("$TUNNELS_DIR"/*.pid)
    
    for pid_file in "${pid_files[@]}"; do
        if [[ ! -f "$pid_file" ]]; then
            continue
        fi
        
        local tunnel_id=$(basename "$pid_file" .pid)
        if is_tunnel_alive "$pid_file"; then
            tunnels+=("$tunnel_id")
            count=$((count + 1))
        else
            # Clean up dead tunnel
            rm -f "$pid_file" "$TUNNELS_DIR/$tunnel_id.config" 2>/dev/null
        fi
    done
    
    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No running tunnels to $action${NC}" >&2
        return 1
    fi
    
    # Display menu to STDERR so it doesn't interfere with return value
    echo -e "${BLUE}Select tunnel to $action:${NC}" >&2
    for i in "${!tunnels[@]}"; do
        local tunnel_id="${tunnels[$i]}"
        local config_file="$TUNNELS_DIR/$tunnel_id.config"
        local name="$tunnel_id"
        local port="?"
        
        if [ -f "$config_file" ]; then
            while IFS= read -r line; do
                case $line in
                    NAME=*) name="${line#NAME=}" ;;
                    PORT=*) port="${line#PORT=}" ;;
                esac
            done < "$config_file" 2>/dev/null
        fi
        
        echo -e "  ${GREEN}$((i+1))${NC}. $name (localhost:$port)" >&2
    done
    
    # Read choice
    read -p "$(echo -e "${YELLOW}Enter number (1-$count) or 'cancel': ${NC}")" choice >&2
    
    if [[ "$choice" == "cancel" ]]; then
        return 1
    fi
    
    # Validate choice
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt $count ]; then
        echo -e "${RED}❌ Invalid selection${NC}" >&2
        return 1
    fi
    
    # RETURN ONLY THE TUNNEL ID — nothing else!
    echo "${tunnels[$((choice-1))]}"
}

# Stop specific tunnel
stop_tunnel() {
    echo -e "${BLUE}🛑 Stopping Specific Tunnel...${NC}"
    
    local tunnel_id=$(select_tunnel "stop")
    if [ $? -ne 0 ] || [ -z "$tunnel_id" ]; then
        return
    fi
    
    local pid_file="$TUNNELS_DIR/$tunnel_id.pid"
    local config_file="$TUNNELS_DIR/$tunnel_id.config"
    local log_file="$LOGS_DIR/$tunnel_id.log"
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${RED}❌ Tunnel '$tunnel_id' not found${NC}"
        return
    fi
    
    local pid=$(cat "$pid_file" 2>/dev/null)
    
    if kill "$pid" 2>/dev/null; then
        # Wait for graceful shutdown
        for i in {1..5}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        
        # Clean up files
        rm -f "$pid_file" "$config_file" 2>/dev/null
        
        echo -e "${GREEN}✅ Tunnel '$tunnel_id' stopped successfully${NC}"
    else
        echo -e "${RED}❌ Failed to stop tunnel '$tunnel_id' (PID: $pid)${NC}"
        rm -f "$pid_file" 2>/dev/null
    fi
}

# Stop all tunnels
stop_all_tunnels() {
    echo -e "${BLUE}🛑 Stopping ALL Tunnels...${NC}"
    
    local count=0
    shopt -s nullglob 2>/dev/null || true
    local pid_files=("$TUNNELS_DIR"/*.pid)
    
    for pid_file in "${pid_files[@]}"; do
        if [[ ! -f "$pid_file" ]]; then
            continue
        fi
        
        local tunnel_id=$(basename "$pid_file" .pid)
        if is_tunnel_alive "$pid_file"; then
            local pid=$(cat "$pid_file" 2>/dev/null)
            
            if kill "$pid" 2>/dev/null; then
                for i in {1..3}; do
                    if ! kill -0 "$pid" 2>/dev/null; then
                        break
                    fi
                    sleep 1
                done
                
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null
                fi
                
                rm -f "$pid_file" "$TUNNELS_DIR/$tunnel_id.config" 2>/dev/null
                echo -e "${GREEN}✅ Stopped: $tunnel_id${NC}"
                count=$((count + 1))
            else
                echo -e "${RED}❌ Failed to stop: $tunnel_id${NC}"
                rm -f "$pid_file" 2>/dev/null
            fi
        else
            # Clean up dead tunnel files
            rm -f "$pid_file" "$TUNNELS_DIR/$tunnel_id.config" 2>/dev/null
        fi
    done
    
    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}No running tunnels to stop${NC}"
    else
        echo -e "${GREEN}✅ Stopped $count tunnel(s)${NC}"
    fi
}

# Show logs for specific tunnel
show_tunnel_logs() {
    echo -e "${BLUE}📋 View Tunnel Logs${NC}"
    
    # Capture only the tunnel ID
    local tunnel_id
    tunnel_id=$(select_tunnel "view logs for") || return
    
    local log_file="$LOGS_DIR/$tunnel_id.log"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${YELLOW}No log file found for tunnel '$tunnel_id'${NC}"
        return
    fi
    
    echo -e "${CYAN}Showing last 25 lines of $log_file:${NC}"
    echo -e "${CYAN}========================================${NC}"
    tail -25 "$log_file"
    
    echo -e "\n${YELLOW}Options:${NC}"
    echo -e "  f) Follow logs in real-time (Ctrl+C to exit)"
    echo -e "  a) Show all logs"
    echo -e "  Enter) Return to menu"
    read -p "$(echo -e "${YELLOW}Your choice: ${NC}")" choice
    
    case "$choice" in
        f|F)
            echo -e "${GREEN}Following logs... (Ctrl+C to exit)${NC}"
            tail -f "$log_file"
            ;;
        a|A)
            echo -e "${GREEN}Showing all logs:${NC}"
            if command -v less &> /dev/null; then
                less "$log_file"
            else
                cat "$log_file"
            fi
            ;;
    esac
}

# Configure defaults
configure_defaults() {
    echo -e "${BLUE}⚙️  Configure Default Settings${NC}"
    
    echo -e "${YELLOW}Current defaults:${NC}"
    echo -e "  Port: $DEFAULT_PORT"
    echo -e "  Protocol: $DEFAULT_PROTOCOL"
    
    local new_port=$(get_input_with_default "New default port" "$DEFAULT_PORT")
    local new_protocol=$(get_input_with_default "New default protocol (http/https)" "$DEFAULT_PROTOCOL")
    
    if [[ "$new_protocol" == "http" || "$new_protocol" == "https" ]]; then
        DEFAULT_PORT="$new_port"
        DEFAULT_PROTOCOL="$new_protocol"
        echo -e "${GREEN}✅ Defaults updated!${NC}"
    else
        echo -e "${RED}❌ Invalid protocol. Keeping old settings.${NC}"
    fi
    
    echo -e "${YELLOW}Note: These changes only apply to this session.${NC}"
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read -r
}

# Show help
show_help() {
    echo -e "${BLUE}❓ Help & Tips${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}What's New in v2.1:${NC}"
    echo -e "  • Run MULTIPLE tunnels simultaneously!"
    echo -e "  • Name your tunnels for easy identification"
    echo -e "  • Stop individual tunnels without affecting others"
    echo -e "  • Real-time status display above menu"
    echo -e ""
    echo -e "${GREEN}Pro Tips:${NC}"
    echo -e "  • Use descriptive names: 'react-app', 'api-server', 'webhook-test'"
    echo -e "  • You can expose different services on different ports at the same time"
    echo -e "  • URLs are temporary — they change every time you restart a tunnel"
    echo -e "  • Use 'Follow logs' to monitor tunnel activity in real-time"
    echo -e ""
    echo -e "${GREEN}Example Workflow:${NC}"
    echo -e "  1. Start tunnel for React app on port 3000 → name it 'frontend'"
    echo -e "  2. Start tunnel for API server on port 8080 → name it 'backend'"
    echo -e "  3. Share both URLs with your team simultaneously!"
    echo -e ""
    echo -e "${YELLOW}Press Enter to return to menu...${NC}"
    read -r
}

# Main function
main() {
    check_dependencies
    
    while true; do
        show_banner
        show_menu
        
        read -r choice
        
        case $choice in
            1) start_tunnel ;;
            2) stop_tunnel ;;
            3) stop_all_tunnels ;;
            4) show_tunnel_logs ;;
            5) configure_defaults ;;
            6) show_help ;;
            0)
                echo -e "${BLUE}🚪 Exiting...${NC}"
                # Ask if user wants to stop all tunnels
                shopt -s nullglob 2>/dev/null || true
                local pid_files=("$TUNNELS_DIR"/*.pid)
                if [ ${#pid_files[@]} -gt 0 ]; then
                    echo -e "${YELLOW}You have running tunnels.${NC}"
                    read -p "Do you want to stop all tunnels before exiting? (Y/n): " confirm
                    if [[ "${confirm,,}" != "n" ]]; then
                        stop_all_tunnels
                    fi
                fi
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Invalid option. Please try again.${NC}"
                sleep 1
                ;;
        esac
        
        echo -e "\n${YELLOW}Press Enter to continue...${NC}"
        read -r
    done
}

# Trap Ctrl+C
trap 'echo -e "\n\n${YELLOW}⚠️  Interrupted. Exiting gracefully...${NC}"; exit 1' INT

# Run main
main
