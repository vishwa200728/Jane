#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#   JANE AI GF Bot — Ubuntu Auto-Installer   ✨ by Vishwa ✨
#   Supports: Root user · sudo user · no-sudo user
# ═══════════════════════════════════════════════════════════════════════

# ── Colors ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; PINK='\033[0;35m'; NC='\033[0m'; BOLD='\033[1m'
DIM='\033[2m'

info()    { echo -e "${CYAN}  ℹ  $1${NC}"; }
success() { echo -e "${GREEN}  ✅  $1${NC}"; }
warn()    { echo -e "${YELLOW}  ⚠️   $1${NC}"; }
error()   { echo -e "${RED}  ❌  $1${NC}"; }
step()    { echo -e "\n${PINK}${BOLD}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; \
            echo -e "${PINK}${BOLD}   $1${NC}"; \
            echo -e "${PINK}${BOLD}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ── Smart sudo handler ─────────────────────────────────────────────────
# Works whether you are: root, a sudo user, or a non-sudo user
# Usage: SUDO <command>  (automatically prepends sudo if needed)
if [[ $EUID -eq 0 ]]; then
    # Already root — no sudo needed
    SUDO=""
    APT="apt"
else
    # Check if sudo is available and user has permission
    if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
        SUDO="sudo"
        APT="sudo apt"
    elif command -v sudo &>/dev/null; then
        # sudo exists but needs password
        SUDO="sudo"
        APT="sudo apt"
        echo -e "${YELLOW}  ⚠️   sudo may ask for your password during installation.${NC}"
    else
        # No sudo — try without (may fail for system packages)
        SUDO=""
        APT="apt"
        warn "sudo not found — system package installation may fail."
        warn "If it fails, run: su -c 'apt install ...' or ask your sysadmin."
    fi
fi

# ── Banner ─────────────────────────────────────────────────────────────
clear 2>/dev/null || true
echo ""
echo -e "${PINK}${BOLD}  ╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${PINK}${BOLD}  ║      💝  JANE AI GF Bot — Ubuntu Installer  💝      ║${NC}"
echo -e "${PINK}${BOLD}  ║                       ✨ by Vishwa ✨               ║${NC}"
echo -e "${PINK}${BOLD}  ╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Detect OS ──────────────────────────────────────────────────────────
if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    info "Detected OS: ${BOLD}$PRETTY_NAME${NC}"
    # Check Ubuntu/Debian
    if [[ "$ID" != "ubuntu" && "$ID_LIKE" != *"debian"* && "$ID" != "debian" ]]; then
        warn "This installer is designed for Ubuntu/Debian."
        warn "Other distros may work but are not officially supported."
    fi
else
    warn "Could not detect OS — continuing anyway."
fi

# Show running mode
if [[ $EUID -eq 0 ]]; then
    info "Running as: ${BOLD}root${NC} (no sudo needed)"
else
    info "Running as: ${BOLD}$USER${NC} (will use: ${SUDO:-no sudo})"
fi

echo ""
read -rp "$(echo -e ${YELLOW}"  Press Enter to start installation, or Ctrl+C to cancel: "${NC})"

# ═══════════════════════════════════════════════════════════════════════
#  STEP 1 — System Packages
# ═══════════════════════════════════════════════════════════════════════
step "STEP 1 — System Packages"

info "Updating package lists..."
if $APT update -qq 2>/dev/null; then
    success "Package lists updated!"
else
    warn "apt update failed — trying to continue with existing package lists."
fi

info "Installing system dependencies..."
$APT install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-full \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    curl \
    wget \
    git \
    build-essential \
    libportaudio2 \
    portaudio19-dev \
    libasound2-dev \
    libsndfile1 \
    lm-sensors \
    net-tools \
    2>/dev/null
APT_EXIT=$?

if [[ $APT_EXIT -eq 0 ]]; then
    success "System packages installed!"
else
    warn "Some packages may have failed (exit code: $APT_EXIT) — continuing..."
    warn "You can manually install missing ones later."
fi

# ═══════════════════════════════════════════════════════════════════════
#  STEP 2 — Python Virtual Environment
# ═══════════════════════════════════════════════════════════════════════
step "STEP 2 — Python Virtual Environment"

VENV_DIR="$HOME/jane_env"

if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment already exists at: $VENV_DIR"
    read -rp "$(echo -e ${YELLOW}"  Recreate it? (y/n, default n): "${NC})" recreate_venv
    if [[ "$recreate_venv" == "y" || "$recreate_venv" == "Y" ]]; then
        rm -rf "$VENV_DIR"
        info "Removed old virtual environment."
    fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment at: $VENV_DIR ..."

    # Try python3 -m venv first
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        success "Virtual environment created!"
    # Some Ubuntu versions need --without-pip
    elif python3 -m venv --without-pip "$VENV_DIR" 2>/dev/null; then
        warn "Created venv without pip — will bootstrap pip manually."
    else
        error "Could not create virtual environment!"
        error "Try: sudo apt install python3-venv python3-full"
        exit 1
    fi
fi

# Activate venv
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
    success "Virtual environment activated: $VENV_DIR"
else
    error "Virtual environment activation failed — $VENV_DIR/bin/activate not found!"
    exit 1
fi

# Bootstrap pip if missing
if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
    info "Bootstrapping pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi

info "Upgrading pip, setuptools, wheel..."
python3 -m pip install --upgrade pip setuptools wheel -q 2>/dev/null
success "pip upgraded!"

# ═══════════════════════════════════════════════════════════════════════
#  STEP 3 — Python Packages
# ═══════════════════════════════════════════════════════════════════════
step "STEP 3 — Python Packages"

# Helper function: install a pip package with clear output
pip_install() {
    local pkg="$1"
    local label="${2:-$1}"
    info "Installing $label..."
    if python3 -m pip install "$pkg" -q --no-warn-script-location 2>/dev/null; then
        success "$label ✓"
        return 0
    else
        warn "$label install failed — some features may not work."
        return 1
    fi
}

pip_install "requests"               "requests (HTTP)"
pip_install "faster-whisper"         "faster-whisper (audio AI)"
pip_install "pillow"                 "Pillow (image processing)"
pip_install "pytesseract"            "pytesseract (OCR)"
pip_install "SpeechRecognition"      "SpeechRecognition (STT fallback)"
pip_install "pydub"                  "pydub (audio conversion)"
pip_install "beautifulsoup4"         "beautifulsoup4 (web scraping)"
pip_install "lxml"                   "lxml (HTML parser)"
pip_install "psutil"                 "psutil (system monitoring)"
pip_install "python-docx"            "python-docx (Word file support)"

echo ""
success "All Python packages installed!"

# ═══════════════════════════════════════════════════════════════════════
#  STEP 4 — Ollama LLM Engine
# ═══════════════════════════════════════════════════════════════════════
step "STEP 4 — Ollama LLM Engine"

if command -v ollama &>/dev/null; then
    OLLAMA_VER=$(ollama --version 2>/dev/null || echo "version unknown")
    success "Ollama already installed: $OLLAMA_VER"
else
    info "Downloading and installing Ollama..."
    echo -e "${DIM}  (This installs to /usr/local/bin/ollama — requires root/sudo)${NC}"

    if curl -fsSL https://ollama.ai/install.sh | sh 2>/dev/null; then
        success "Ollama installed successfully!"
    else
        warn "Ollama install script failed."
        warn "Manual install: curl -fsSL https://ollama.ai/install.sh | sh"
        warn "Or download from: https://ollama.ai/download"
    fi
fi

# ── Start Ollama service ──────────────────────────────────────────────
info "Starting Ollama service..."

# Try systemctl (Ubuntu with systemd)
OLLAMA_STARTED=false
if command -v systemctl &>/dev/null; then
    # Only try systemctl if the service file exists
    if [[ -f /etc/systemd/system/ollama.service ]] || \
       [[ -f /usr/lib/systemd/system/ollama.service ]]; then
        $SUDO systemctl enable ollama 2>/dev/null || true
        $SUDO systemctl start  ollama 2>/dev/null || true
        sleep 3
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            success "Ollama started via systemd!"
            OLLAMA_STARTED=true
        fi
    fi
fi

# Try manual start if systemd didn't work
if [[ "$OLLAMA_STARTED" == "false" ]]; then
    info "Starting Ollama manually in background..."
    # Kill any existing stuck ollama process
    pkill -f "ollama serve" 2>/dev/null || true
    sleep 1
    nohup ollama serve > /tmp/ollama_jane.log 2>&1 &
    OLLAMA_PID=$!
    info "Ollama PID: $OLLAMA_PID (log: /tmp/ollama_jane.log)"

    # Wait up to 15 seconds for Ollama to respond
    for i in {1..15}; do
        sleep 1
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            success "Ollama is running! (started in ${i}s)"
            OLLAMA_STARTED=true
            break
        fi
        echo -ne "  Waiting for Ollama... ${i}s\r"
    done
    echo ""
fi

if [[ "$OLLAMA_STARTED" == "false" ]]; then
    warn "Ollama is not responding yet."
    warn "It may still be starting — try running 'ollama serve' manually."
fi

# ═══════════════════════════════════════════════════════════════════════
#  STEP 5 — Pull Ollama Models
# ═══════════════════════════════════════════════════════════════════════
step "STEP 5 — Ollama Models"

echo ""
echo -e "  ${YELLOW}${BOLD}Which model would you like to pull?${NC}"
echo -e "  ${DIM}(All models support vision + chat for Jane)${NC}"
echo ""
echo -e "  ${BOLD}1.${NC} gemma3:12b-cloud       ${GREEN}← RECOMMENDED${NC}"
echo -e "     Vision + chat · Best quality for Jane · ~7GB"
echo ""
echo -e "  ${BOLD}2.${NC} gemma3:27b-cloud"
echo -e "     Vision + chat · Highest quality · ~15GB"
echo ""
echo -e "  ${BOLD}3.${NC} gemma4:31b-cloud"
echo -e "     Vision + chat · Next-gen · ~18GB"
echo ""
echo -e "  ${BOLD}4.${NC} deepseek-v3.2:cloud"
echo -e "     Chat · Fast & smart · ~2GB"
echo ""
echo -e "  ${BOLD}5.${NC} Pull multiple models"
echo -e "     Choose more than one"
echo ""
echo -e "  ${BOLD}6.${NC} Skip"
echo -e "     I'll pull manually later"
echo ""

read -rp "$(echo -e ${PINK}"  Choose (1/2/3/4/5/6): "${NC})" model_choice

# ── Pull function ─────────────────────────────────────────────────────
pull_model() {
    local model_name="$1"
    local display_name="$2"
    info "Pulling ${display_name} — this may take a while..."
    echo -e "  ${DIM}(Download size varies — keep terminal open)${NC}"
    if ollama pull "$model_name" 2>&1; then
        success "${display_name} ready!"
    else
        warn "${display_name} pull failed."
        warn "Try manually: ollama pull ${model_name}"
    fi
}

case $model_choice in
    1)
        pull_model "gemma3:12b"    "gemma3:12b-cloud"
        ;;
    2)
        pull_model "gemma3:27b"    "gemma3:27b-cloud"
        ;;
    3)
        pull_model "gemma4:31b"    "gemma4:31b-cloud"
        ;;
    4)
        pull_model "deepseek-v3:7b" "deepseek-v3.2:cloud"
        ;;
    5)
        echo ""
        echo -e "  ${CYAN}Select models to pull (space-separated numbers, e.g: 1 4):${NC}"
        echo -e "  1=gemma3:12b  2=gemma3:27b  3=gemma4:31b  4=deepseek-v3.2"
        read -rp "  Your choices: " multi_choices
        for choice in $multi_choices; do
            case $choice in
                1) pull_model "gemma3:12b"    "gemma3:12b-cloud" ;;
                2) pull_model "gemma3:27b"    "gemma3:27b-cloud" ;;
                3) pull_model "gemma4:31b"    "gemma4:31b-cloud" ;;
                4) pull_model "deepseek-v3:7b" "deepseek-v3.2:cloud" ;;
                *) warn "Unknown choice: $choice — skipping." ;;
            esac
        done
        ;;
    6)
        warn "Skipping model download."
        info "Pull later with: ollama pull gemma3:12b"
        ;;
    *)
        warn "Invalid choice — skipping model download."
        info "Pull later with: ollama pull gemma3:12b"
        ;;
esac

# ── List pulled models ────────────────────────────────────────────────
echo ""
info "Currently available Ollama models:"
ollama list 2>/dev/null || warn "Could not list models (is Ollama running?)"

# ═══════════════════════════════════════════════════════════════════════
#  STEP 6 — faster-whisper Info
# ═══════════════════════════════════════════════════════════════════════
step "STEP 6 — faster-whisper Audio Model"

echo ""
echo -e "  ${CYAN}faster-whisper downloads its AI model automatically${NC}"
echo -e "  ${CYAN}on the FIRST time you send a voice note to Jane.${NC}"
echo ""
echo -e "  ${BOLD}Available whisper model sizes:${NC}"
echo -e "  ┌─────────────┬──────────┬─────────────────────────────┐"
echo -e "  │ ${BOLD}Model${NC}       │ ${BOLD}Size${NC}     │ ${BOLD}Notes${NC}                       │"
echo -e "  ├─────────────┼──────────┼─────────────────────────────┤"
echo -e "  │ tiny        │ ~75 MB   │ Fastest, basic accuracy     │"
echo -e "  │ base        │ ~150 MB  │ ${GREEN}Default — good balance${NC}       │"
echo -e "  │ small       │ ~500 MB  │ Better accuracy             │"
echo -e "  │ medium      │ ~1.5 GB  │ High accuracy               │"
echo -e "  │ large-v3    │ ~3 GB    │ Best accuracy, slow on CPU  │"
echo -e "  └─────────────┴──────────┴─────────────────────────────┘"
echo ""
echo -e "  ${DIM}Cached at: ~/.cache/huggingface/hub/${NC}"
echo ""

read -rp "$(echo -e ${YELLOW}"  Pre-download whisper model now? (y/n, default n): "${NC})" dl_whisper

if [[ "$dl_whisper" == "y" || "$dl_whisper" == "Y" ]]; then
    echo -e "  Select size: 1=tiny  2=base  3=small  4=medium  5=large-v3"
    read -rp "  Choice (default 2=base): " wsize_choice
    case $wsize_choice in
        1) WSIZE="tiny"     ;;
        3) WSIZE="small"    ;;
        4) WSIZE="medium"   ;;
        5) WSIZE="large-v3" ;;
        *) WSIZE="base"     ;;
    esac
    info "Pre-downloading faster-whisper model: $WSIZE ..."
    python3 -c "
from faster_whisper import WhisperModel
print(f'  Downloading {\"$WSIZE\"} model...')
m = WhisperModel('$WSIZE', device='cpu', compute_type='int8')
print('  Model ready!')
" 2>/dev/null && success "faster-whisper $WSIZE model downloaded!" \
    || warn "Pre-download failed — it will auto-download on first use."
else
    success "faster-whisper will auto-download 'base' model on first voice message."
fi

# ═══════════════════════════════════════════════════════════════════════
#  STEP 7 — Locate or Copy ai_gf_bot.py
# ═══════════════════════════════════════════════════════════════════════
step "STEP 7 — Bot File Location"

BOT_FILE="$HOME/ai_gf_bot.py"

if [[ -f "$BOT_FILE" ]]; then
    success "ai_gf_bot.py already found at: $BOT_FILE"
else
    # Search common locations
    FOUND_BOT=""
    for search_path in \
        "$(pwd)/ai_gf_bot.py" \
        "$HOME/Downloads/ai_gf_bot.py" \
        "$HOME/Desktop/ai_gf_bot.py" \
        "/tmp/ai_gf_bot.py"
    do
        if [[ -f "$search_path" ]]; then
            FOUND_BOT="$search_path"
            break
        fi
    done

    if [[ -n "$FOUND_BOT" ]]; then
        info "Found bot at: $FOUND_BOT"
        cp "$FOUND_BOT" "$BOT_FILE"
        success "Copied to: $BOT_FILE"
    else
        warn "ai_gf_bot.py not found in common locations."
        echo ""
        echo -e "  ${YELLOW}Please copy ai_gf_bot.py to your home folder:${NC}"
        echo -e "  ${BOLD}  cp /path/to/ai_gf_bot.py $BOT_FILE${NC}"
        echo ""
        read -rp "$(echo -e ${CYAN}"  Enter the full path to ai_gf_bot.py (or Enter to skip): "${NC})" manual_path
        if [[ -n "$manual_path" && -f "$manual_path" ]]; then
            cp "$manual_path" "$BOT_FILE"
            success "Copied to: $BOT_FILE"
        else
            warn "Bot file not set. You must copy it manually before running Jane."
        fi
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
#  STEP 8 — Create Launcher Script
# ═══════════════════════════════════════════════════════════════════════
step "STEP 8 — Launcher Script"

LAUNCHER="$HOME/start_jane.sh"

cat > "$LAUNCHER" << 'LAUNCHER_HEREDOC'
#!/bin/bash
# ════════════════════════════════════════
#   Jane AI GF Bot — Launcher
#   ✨ by Vishwa
# ════════════════════════════════════════

PINK='\033[0;35m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${PINK}  💝 Starting Jane AI GF Bot... ✨ by Vishwa${NC}"

# Activate virtual environment
VENV_DIR="$HOME/jane_env"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}  ✅ Virtual env activated${NC}"
else
    echo -e "${YELLOW}  ⚠️  Virtual env not found at $VENV_DIR${NC}"
fi

# Start Ollama if not already running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}  ⚡ Starting Ollama...${NC}"
    pkill -f "ollama serve" 2>/dev/null || true
    sleep 1
    nohup ollama serve > /tmp/ollama_jane.log 2>&1 &
    # Wait for Ollama to be ready
    for i in {1..15}; do
        sleep 1
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Ollama ready! (${i}s)${NC}"
            break
        fi
    done
else
    echo -e "${GREEN}  ✅ Ollama already running${NC}"
fi

# Run Jane bot
BOT="$HOME/ai_gf_bot.py"
if [[ -f "$BOT" ]]; then
    echo -e "${PINK}  💝 Launching Jane...${NC}"
    echo ""
    python3 "$BOT" "$@"
else
    echo -e "\033[0;31m  ❌ ai_gf_bot.py not found at: $BOT\033[0m"
    echo "  Copy it with: cp /path/to/ai_gf_bot.py $BOT"
    exit 1
fi
LAUNCHER_HEREDOC

chmod +x "$LAUNCHER"
success "Launcher created: $LAUNCHER"

# ═══════════════════════════════════════════════════════════════════════
#  STEP 9 — Shell Alias
# ═══════════════════════════════════════════════════════════════════════
step "STEP 9 — Shell Alias"

# Detect shell config file
SHELL_RC="$HOME/.bashrc"
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ "$SHELL" == *"fish"* ]]; then
    SHELL_RC="$HOME/.config/fish/config.fish"
fi

if ! grep -q "alias jane=" "$SHELL_RC" 2>/dev/null; then
    {
        echo ""
        echo "# ── Jane AI GF Bot  ✨ by Vishwa ──"
        echo "alias jane='$LAUNCHER'"
        echo "alias jane-log='tail -f ~/.ai_gf_jane.log'"
    } >> "$SHELL_RC"
    success "Alias 'jane' added to $SHELL_RC"
    success "Alias 'jane-log' added (view live logs)"
    info "To use immediately: source $SHELL_RC"
else
    success "Alias 'jane' already exists in $SHELL_RC"
fi

# ═══════════════════════════════════════════════════════════════════════
#  STEP 10 — Optional Systemd Auto-Start Service
# ═══════════════════════════════════════════════════════════════════════
step "STEP 10 — Auto-Start Service (Optional)"

echo ""
echo -e "  ${DIM}Installs a systemd service so Jane starts automatically on boot.${NC}"
echo -e "  ${DIM}Requires sudo/root to write to /etc/systemd/system/${NC}"
echo ""
read -rp "$(echo -e ${YELLOW}"  Install systemd auto-start? (y/n): "${NC})" install_service

if [[ "$install_service" == "y" || "$install_service" == "Y" ]]; then
    SERVICE_FILE="/etc/systemd/system/jane-bot.service"

    # Check if we can write to /etc/systemd/system/
    if [[ $EUID -eq 0 ]] || (command -v sudo &>/dev/null && sudo -n test -w /etc/systemd/system/ 2>/dev/null); then
        # Write service file
        $SUDO tee "$SERVICE_FILE" > /dev/null << SERVICE_HEREDOC
[Unit]
Description=Jane AI GF Telegram Bot  ✨ by Vishwa
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$HOME
ExecStartPre=/bin/bash -c 'until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do sleep 2; done'
ExecStart=$LAUNCHER
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
Environment=HOME=$HOME
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
SERVICE_HEREDOC

        $SUDO systemctl daemon-reload 2>/dev/null
        $SUDO systemctl enable jane-bot 2>/dev/null
        success "Service installed: $SERVICE_FILE"
        info "Start now:  sudo systemctl start jane-bot"
        info "Check logs: journalctl -u jane-bot -f"
        info "Status:     sudo systemctl status jane-bot"
    else
        warn "Cannot write to /etc/systemd/system/ — skipping service."
        warn "To install manually, run this script as root or with sudo."
    fi
else
    info "Skipping systemd service."
fi

# ═══════════════════════════════════════════════════════════════════════
#  FINAL CHECK — Verify everything installed correctly
# ═══════════════════════════════════════════════════════════════════════
step "Final Verification"

echo ""

# Python
if python3 --version &>/dev/null; then
    success "Python3: $(python3 --version)"
else
    warn "Python3: NOT FOUND"
fi

# Virtual env
if [[ -f "$VENV_DIR/bin/python3" ]]; then
    success "Virtual env: $VENV_DIR ✓"
else
    warn "Virtual env: NOT FOUND at $VENV_DIR"
fi

# pip packages
source "$VENV_DIR/bin/activate" 2>/dev/null || true
echo ""
info "Checking installed Python packages..."
for pkg in requests faster_whisper PIL pytesseract psutil bs4 docx; do
    if python3 -c "import $pkg" 2>/dev/null; then
        success "  import $pkg ✓"
    else
        warn "  import $pkg ✗ (may need reinstall)"
    fi
done

# Ollama
echo ""
if command -v ollama &>/dev/null; then
    success "Ollama binary: $(which ollama)"
else
    warn "Ollama binary: NOT FOUND in PATH"
fi

if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    success "Ollama server: RUNNING at localhost:11434"
    # Show available models
    echo ""
    info "Available models:"
    ollama list 2>/dev/null | while read -r line; do
        echo "    $line"
    done
else
    warn "Ollama server: NOT RUNNING"
    info "Start it with: ollama serve"
fi

# Tools
echo ""
for tool in ffmpeg tesseract; do
    if command -v $tool &>/dev/null; then
        success "$tool: $(which $tool)"
    else
        warn "$tool: NOT FOUND — install with: sudo apt install $tool"
    fi
done

# Bot file
echo ""
if [[ -f "$BOT_FILE" ]]; then
    success "Bot file: $BOT_FILE ✓"
else
    warn "Bot file: NOT FOUND at $BOT_FILE"
    warn "Copy it: cp /path/to/ai_gf_bot.py $BOT_FILE"
fi

# ═══════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════
echo ""
echo -e "${PINK}${BOLD}  ╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${PINK}${BOLD}  ║          🎉  Installation Complete!  🎉              ║${NC}"
echo -e "${PINK}${BOLD}  ╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}${BOLD}File Locations:${NC}"
echo -e "  📁 Bot:       ${BOLD}$BOT_FILE${NC}"
echo -e "  🚀 Launcher:  ${BOLD}$LAUNCHER${NC}"
echo -e "  🐍 Venv:      ${BOLD}$VENV_DIR${NC}"
echo -e "  📋 Log:       ${BOLD}~/.ai_gf_jane.log${NC}"
echo -e "  ⚙️  Config:    ${BOLD}~/.ai_gf_config.json${NC}"
echo ""
echo -e "  ${CYAN}${BOLD}Before running, get these FREE API keys:${NC}"
echo -e "  🌤  OpenWeatherMap → ${BOLD}openweathermap.org/api${NC}"
echo -e "      (Free tier: 1,000 calls/day)"
echo -e "  📰  NewsAPI        → ${BOLD}newsapi.org/register${NC}"
echo -e "      (Free tier: 100 calls/day)"
echo -e "  🤖  Telegram Bot   → ${BOLD}@BotFather${NC} on Telegram → /newbot"
echo ""
echo -e "  ${YELLOW}${BOLD}▶  How to Run Jane:${NC}"
echo -e ""
echo -e "  ${BOLD}Option 1${NC} — Use the alias (after reloading shell):"
echo -e "  ${GREEN}    source ~/.bashrc && jane${NC}"
echo ""
echo -e "  ${BOLD}Option 2${NC} — Run directly:"
echo -e "  ${GREEN}    bash $LAUNCHER${NC}"
echo ""
echo -e "  ${BOLD}Option 3${NC} — Manual:"
echo -e "  ${GREEN}    source $VENV_DIR/bin/activate${NC}"
echo -e "  ${GREEN}    ollama serve &${NC}"
echo -e "  ${GREEN}    python3 $BOT_FILE${NC}"
echo ""
echo -e "  ${BOLD}View logs:${NC}"
echo -e "  ${GREEN}    tail -f ~/.ai_gf_jane.log${NC}"
echo -e "  ${GREEN}    jane-log${NC}  ${DIM}(after reloading shell)${NC}"
echo ""
echo -e "  ${PINK}${BOLD}  ✨ by Vishwa  💝  Enjoy Jane!${NC}"
echo ""
