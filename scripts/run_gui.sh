#!/usr/bin/env bash
# Launch the NethunterZ PyQt5 GUI application
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GUI_DIR="$PROJECT_ROOT/gui"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

PYTHON="${PYTHON:-python3}"

check_requirements() {
    local missing=()
    for pkg in PyQt5 serial matplotlib; do
        "$PYTHON" -c "import $pkg" 2>/dev/null || missing+=("$pkg")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Missing Python packages: ${missing[*]}"
        log_info "Installing requirements..."
        pip3 install -r "$GUI_DIR/requirements.txt"
    fi
}

setup_display() {
    # Handle headless environments
    if [[ -z "${DISPLAY:-}" ]] && [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v Xvfb &>/dev/null; then
            log_info "Starting virtual display (Xvfb)..."
            Xvfb :99 -screen 0 1920x1080x24 &
            export DISPLAY=:99
            sleep 1
        else
            log_warn "No DISPLAY set and Xvfb not available."
            log_warn "Install Xvfb: sudo apt-get install xvfb"
        fi
    fi
}

log_info "NethunterZ GUI Launcher"
log_info "Python: $($PYTHON --version 2>&1)"
check_requirements
setup_display
log_info "Starting GUI from $GUI_DIR..."
cd "$GUI_DIR"
exec "$PYTHON" main.py "$@"
