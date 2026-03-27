#!/usr/bin/env bash
# Install all NethunterZ project dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_section() { echo -e "\n${CYAN}══ $* ══${NC}"; }

OS=$(uname -s)
PYTHON="${PYTHON:-python3}"
PIP="${PIP:-pip3}"

check_python() {
    if ! command -v "$PYTHON" &>/dev/null; then
        log_error "Python 3 not found. Install from https://python.org"
        exit 1
    fi
    PYVER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
    log_info "Python version: $PYVER"
}

install_system_deps() {
    log_section "System Dependencies"
    case "$OS" in
        Linux)
            if command -v apt-get &>/dev/null; then
                log_info "Installing apt packages..."
                sudo apt-get update -qq
                sudo apt-get install -y --no-install-recommends \
                    python3-pip python3-dev python3-venv \
                    libusb-1.0-0 libssl-dev \
                    gcc make cmake ninja-build \
                    git curl wget
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y python3-pip python3-devel libusb-devel openssl-devel cmake ninja-build
            fi
            ;;
        Darwin)
            if command -v brew &>/dev/null; then
                log_info "Installing Homebrew packages..."
                brew install python cmake ninja libusb openssl
            else
                log_warn "Homebrew not found. Visit https://brew.sh"
            fi
            ;;
        *)
            log_warn "Unsupported OS: $OS – skipping system deps"
            ;;
    esac
}

install_python_deps() {
    log_section "Python Dependencies"
    log_info "Installing GUI requirements..."
    "$PIP" install --upgrade pip wheel
    "$PIP" install -r "$PROJECT_ROOT/gui/requirements.txt"
    log_info "Installing esptool..."
    "$PIP" install esptool
    log_info "Installing pytest and test tools..."
    "$PIP" install pytest pytest-cov pytest-json-report
    log_info "Installing development extras..."
    "$PIP" install black flake8 mypy || log_warn "Linters optional, continuing..."
}

install_platformio() {
    log_section "PlatformIO"
    if command -v pio &>/dev/null; then
        log_info "PlatformIO already installed ($(pio --version))"
    else
        log_info "Installing PlatformIO..."
        "$PIP" install platformio
        log_info "Installing PlatformIO ESP32 platforms..."
        pio pkg install --global --platform "espressif32"
    fi
}

install_esp_idf() {
    log_section "ESP-IDF (Optional)"
    if [[ -n "${IDF_PATH:-}" ]]; then
        log_info "ESP-IDF already configured at: $IDF_PATH"
    else
        log_warn "ESP-IDF not configured. For advanced builds:"
        log_warn "  https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/"
    fi
}

print_summary() {
    log_section "Installation Summary"
    log_info "✔ System dependencies installed"
    log_info "✔ Python packages installed"
    log_info "✔ PlatformIO installed"
    echo ""
    log_info "Next steps:"
    echo "  1. Flash firmware:  ./scripts/flash_firmware.sh --build"
    echo "  2. Launch GUI:      ./scripts/run_gui.sh"
    echo "  3. Run tests:       cd sandbox && pytest"
}

log_info "NethunterZ Dependency Installer"
log_info "OS: $OS | Python: $($PYTHON --version 2>&1)"
check_python
install_system_deps
install_python_deps
install_platformio
install_esp_idf
print_summary
