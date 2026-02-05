#!/usr/bin/env bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          TunnelFlare Installation Wizard           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "Choose installation method:"
echo -e "${GREEN}1) Local Virtual Environment (Recommended)${NC}"
echo "   - Creates a valid python venv in this folder."
echo "   - Installs dependencies isolated from system."
echo "   - Creates a 'run.sh' script to launch the app."
echo ""
echo -e "${GREEN}2) Pipx (Isolated Application)${NC}"
echo "   - Installs as a global command 'tunnelflare'."
echo "   - Requires 'pipx' to be installed."
echo ""
echo -e "${GREEN}3) User Install (pip install --user)${NC}"
echo "   - Installs to ~/.local/bin."
echo "   - WARNING: May conflict with system packages on some distros."
echo ""

read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo -e "\n${BLUE}Installing via Virtual Environment...${NC}"
        
        # Check for python3-venv if on Debian/Ubuntu (common issue)
        if [ -f /etc/debian_version ] && ! dpkg -s python3-venv &> /dev/null; then
            echo -e "${YELLOW}Note: You might need 'python3-venv' installed.${NC}"
        fi

        python3 -m venv .venv
        
        echo -e "${BLUE}Activating venv and installing dependencies...${NC}"
        source .venv/bin/activate
        pip install --upgrade pip
        pip install .
        
        # Create run script
        cat > run.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/main.py"
EOF
        chmod +x run.sh
        
        echo -e "\n${GREEN}✅ Installation Complete!${NC}"
        echo -e "You can run the app using: ${YELLOW}./run.sh${NC}"
        ;;
        
    2)
        echo -e "\n${BLUE}Installing via Pipx...${NC}"
        if ! command -v pipx &> /dev/null; then
            echo -e "${RED}❌ Error: 'pipx' is not installed or not in PATH.${NC}"
            echo "Please install pipx first (e.g., 'sudo apt install pipx' or 'sudo zypper install pipx')"
            exit 1
        fi
        
        pipx install . --force
        
        echo -e "\n${GREEN}✅ Installation Complete!${NC}"
        echo -e "You can run the app using: ${YELLOW}tunnelflare${NC}"
        ;;
        
    3)
        echo -e "\n${BLUE}Installing via User Install...${NC}"
        
        # Check for managed environment
        if pip install --user . 2>&1 | grep -q "externally-managed-environment"; then
            echo -e "${YELLOW}⚠️  Detected managed environment (PEP 668).${NC}"
            read -p "Do you want to force install with --break-system-packages? (y/N): " confirm
            if [[ "${confirm,,}" == "y" ]]; then
                pip install --user . --break-system-packages
            else
                echo -e "${RED}Aborted.${NC}"
                exit 1
            fi
        else
            pip install --user .
        fi
        
        echo -e "\n${GREEN}✅ Installation Complete!${NC}"
        echo -e "Ensure ~/.local/bin is in your PATH."
        echo -e "You can run the app using: ${YELLOW}python3 main.py${NC} (or 'tunnelflare' if in path)"
        ;;
        
    *)
        echo -e "${RED}Invalid choice.${NC}"
        exit 1
        ;;
esac
