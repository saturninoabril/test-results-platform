#!/bin/bash
# Generate locally-trusted SSL certificates for local development using mkcert
# This script creates certificates that are automatically trusted by browsers

set -e

CERT_DIR="certs"
KEY_FILE="${CERT_DIR}/localhost.key"
CERT_FILE="${CERT_DIR}/localhost.crt"

# Colors for output
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
CYAN='\033[36m'
RESET='\033[0m'

echo -e "${BLUE}Generating locally-trusted SSL certificates using mkcert...${RESET}"

# Check if mkcert is installed
if ! command -v mkcert >/dev/null 2>&1; then
    echo -e "${RED}❌ mkcert is not installed${RESET}"
    echo -e "${YELLOW}Please install mkcert first:${RESET}"
    echo ""
    echo -e "${CYAN}macOS (with Homebrew):${RESET}"
    echo -e "  brew install mkcert"
    echo ""
    echo -e "${CYAN}Linux:${RESET}"
    echo -e "  # Ubuntu/Debian:"
    echo -e "  sudo apt install libnss3-tools"
    echo -e "  wget -O mkcert https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v*-linux-amd64"
    echo -e "  chmod +x mkcert && sudo mv mkcert /usr/local/bin/"
    echo ""
    echo -e "${CYAN}Windows:${RESET}"
    echo -e "  choco install mkcert"
    echo -e "  # or download from: https://github.com/FiloSottile/mkcert/releases"
    echo ""
    echo -e "${CYAN}More info: https://github.com/FiloSottile/mkcert${RESET}"
    exit 1
fi

# Create certificate directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Install the local CA if it hasn't been installed yet
echo -e "${CYAN}Setting up local CA (this may prompt for your password)...${RESET}"
mkcert -install

# Generate certificate for localhost and common development domains
echo -e "${CYAN}Generating certificate for localhost and development domains...${RESET}"
cd "$CERT_DIR"
mkcert -key-file localhost.key -cert-file localhost.crt localhost 127.0.0.1 ::1 *.localhost
cd ..

# Set appropriate permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo -e "${GREEN}✅ SSL certificates generated successfully with mkcert!${RESET}"
echo -e "${YELLOW}Certificate: ${CERT_FILE}${RESET}"
echo -e "${YELLOW}Private Key: ${KEY_FILE}${RESET}"
echo -e "${YELLOW}Local CA installed in system trust stores${RESET}"
echo ""
echo -e "${CYAN}The development server will be available at:${RESET}"
echo -e "${GREEN}• https://localhost:8443 (HTTPS) - No browser warnings!${RESET}"
echo -e "${GREEN}• http://localhost:8000 (HTTP)${RESET}"
echo ""
echo -e "${CYAN}Benefits of mkcert:${RESET}"
echo -e "${YELLOW}• Zero browser security warnings${RESET}"
echo -e "${YELLOW}• Works with all browsers and tools${RESET}"
echo -e "${YELLOW}• Automatically trusted by system${RESET}"
echo -e "${YELLOW}• No manual certificate trust steps needed${RESET}"