#!/bin/bash
# Helper script for mkcert certificate management
# Since mkcert automatically handles trust, this script provides info and troubleshooting

set -e

# Colors for output
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
CYAN='\033[36m'
RESET='\033[0m'

echo -e "${BLUE}mkcert Certificate Management${RESET}"
echo ""

# Check if mkcert is installed
if ! command -v mkcert >/dev/null 2>&1; then
    echo -e "${RED}❌ mkcert is not installed${RESET}"
    echo -e "${YELLOW}Run 'make dev-certs' to get installation instructions${RESET}"
    exit 1
fi

# Check if local CA is installed
if mkcert -CAROOT >/dev/null 2>&1; then
    CAROOT=$(mkcert -CAROOT)
    if [ -f "$CAROOT/rootCA.pem" ]; then
        echo -e "${GREEN}✅ mkcert local CA is installed${RESET}"
        echo -e "${CYAN}CA Root: $CAROOT${RESET}"
    else
        echo -e "${YELLOW}⚠️  mkcert local CA not found${RESET}"
        echo -e "${CYAN}Installing local CA...${RESET}"
        mkcert -install
    fi
else
    echo -e "${RED}❌ Unable to check mkcert CA status${RESET}"
    exit 1
fi

# Check certificate status
if [ -f "certs/localhost.crt" ] && [ -f "certs/localhost.key" ]; then
    echo -e "${GREEN}✅ Development certificates exist${RESET}"
    echo -e "${CYAN}Certificate: certs/localhost.crt${RESET}"
    echo -e "${CYAN}Private Key: certs/localhost.key${RESET}"
else
    echo -e "${YELLOW}⚠️  Development certificates not found${RESET}"
    echo -e "${CYAN}Run 'make dev-certs' to generate certificates${RESET}"
fi

echo ""
echo -e "${CYAN}mkcert Benefits:${RESET}"
echo -e "${YELLOW}• Certificates are automatically trusted by all browsers${RESET}"
echo -e "${YELLOW}• No manual certificate trust steps needed${RESET}"
echo -e "${YELLOW}• Works with Chrome, Firefox, Safari, Edge, and more${RESET}"
echo -e "${YELLOW}• Also works with curl, wget, and other tools${RESET}"

echo ""
echo -e "${CYAN}Troubleshooting:${RESET}"
echo -e "${YELLOW}• If you still see browser warnings, restart your browser${RESET}"
echo -e "${YELLOW}• For corporate networks, you may need additional configuration${RESET}"
echo -e "${YELLOW}• Run 'mkcert -uninstall' to remove the local CA if needed${RESET}"