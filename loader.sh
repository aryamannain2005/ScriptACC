#!/usr/bin/env bash
# ==============================================================================
# ScriptACC – Bulletproof One-Click Web Loader (macOS & Linux)
# Usage: curl -sSL https://tinyurl.com/<your-alias> | bash
# ==============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}==================================================${NC}"
echo -e "${GREEN}         ScriptACC AI Assistant (macOS Loader)    ${NC}"
echo -e "${CYAN}==================================================${NC}"

# 1. Directory Setup
WORKSPACE="$HOME/.scriptacc"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# 2. Check Python
PYTHON_BIN=""
for py in "/opt/anaconda3/bin/python" "python3" "python"; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON_BIN=$(command -v "$py")
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}[-] Python 3 not found. Please install Python 3.${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Using Python: ${PYTHON_BIN}${NC}"

# 3. Check Tesseract OCR (macOS Homebrew)
if ! command -v tesseract >/dev/null 2>&1; then
    echo -e "${YELLOW}[*] Installing Tesseract OCR via Homebrew...${NC}"
    if command -v brew >/dev/null 2>&1; then
        brew install tesseract
    fi
fi

# 4. Download latest project archive from GitHub
REPO_ZIP_URL="https://github.com/aryamannain2005/ScriptACC/archive/refs/heads/main.zip"
echo -e "${CYAN}[*] Fetching latest ScriptACC files...${NC}"
curl -sSL "$REPO_ZIP_URL" -o update.zip 2>/dev/null || true

if [ -f "update.zip" ]; then
    unzip -q -o update.zip 2>/dev/null || true
    rm -f update.zip
    if [ -d "ScriptACC-main" ]; then
        cp -r ScriptACC-main/* . 2>/dev/null || true
        rm -rf ScriptACC-main
    fi
fi

# 5. Install Dependencies
echo -e "${CYAN}[*] Installing dependencies...${NC}"
"$PYTHON_BIN" -m pip install -r requirements.txt --quiet --disable-pip-version-check

# 6. Ensure Ollama & Server are running
if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
    if command -v ollama >/dev/null 2>&1; then
        echo -e "${CYAN}[*] Starting Ollama serve...${NC}"
        nohup ollama serve >/dev/null 2>&1 &
        sleep 2
    fi
fi

if ! pgrep -f "uvicorn server:app" >/dev/null 2>&1; then
    echo -e "${CYAN}[*] Starting C2 Gateway server on port 8000...${NC}"
    nohup "$PYTHON_BIN" -m uvicorn server:app --host 0.0.0.0 --port 8000 >/dev/null 2>&1 &
    sleep 1
fi

echo -e "\n${GREEN}==================================================${NC}"
echo -e "${GREEN} [SUCCESS] ScriptACC is ACTIVE and RUNNING!       ${NC}"
echo -e "${GREEN}==================================================${NC}"
echo -e " Hotkeys Active (Option + Key):"
echo -e "   - ⌥ + M : Multi-MCQ Solver"
echo -e "   - ⌥ + 8 : Coding Solver (DSA)"
echo -e "   - ⌥ + 9 : FullStack / SQL / Web / Debug"
echo -e "   - ⌥ + 0 : Game & Puzzle Solver"
echo -e "   - ⌥ + B : Add SS to Buffer"
echo -e "   - ⌥ + F : Auto-Type Solution"
echo -e "   - ⌥ + G : Ghost-Type (Stealth)"
echo -e "   - ⌥ + R : Pause / Resume Typing"
echo -e "   - ⌥ + E : Stop Typing"
echo -e "   - ⌥ + D : Show / Hide Overlay"
echo -e "   - ⌥ + N : Dim 9% (Stealth)"
echo -e "   - ⌥ + I : Show Hotkey Guide"
echo -e "   - ⌥ + ⇧ + X : Emergency Exit"
echo -e "${CYAN}==================================================${NC}\n"

# Run Client
"$PYTHON_BIN" capture_ocr.py
