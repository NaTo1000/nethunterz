#!/usr/bin/env bash
# Start the NRF24L01+ dual-module runtime
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NRF_DIR="$PROJECT_ROOT/nrf"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

PYTHON="${PYTHON:-python3}"
CE_A="${CE_A:-22}"
CSN_A="${CSN_A:-21}"
CE_B="${CE_B:-17}"
CSN_B="${CSN_B:-16}"
SCAN_INTERVAL="${SCAN_INTERVAL:-30}"
LOG_FILE="${LOG_FILE:-nrf_scan.jsonl}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Run NRF24L01+ dual-module frequency scan and hop runtime

Options:
  --ce-a GPIO      CE pin for radio A (default: $CE_A)
  --csn-a GPIO     CSN pin for radio A (default: $CSN_A)
  --ce-b GPIO      CE pin for radio B (default: $CE_B)
  --csn-b GPIO     CSN pin for radio B (default: $CSN_B)
  -i, --interval   Scan interval in seconds (default: $SCAN_INTERVAL)
  -l, --log FILE   Log output file (default: $LOG_FILE)
  -h, --help       Show this help
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ce-a)    CE_A="$2"; shift 2 ;;
        --csn-a)   CSN_A="$2"; shift 2 ;;
        --ce-b)    CE_B="$2"; shift 2 ;;
        --csn-b)   CSN_B="$2"; shift 2 ;;
        -i|--interval) SCAN_INTERVAL="$2"; shift 2 ;;
        -l|--log)  LOG_FILE="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

log_info "NethunterZ NRF24L01+ Runtime"
log_info "Radio A: CE=$CE_A CSN=$CSN_A"
log_info "Radio B: CE=$CE_B CSN=$CSN_B"
log_info "Scan interval: ${SCAN_INTERVAL}s | Log: $LOG_FILE"

check_permissions() {
    if [[ -d /sys/class/gpio ]]; then
        if [[ ! -w /sys/class/gpio/export ]]; then
            log_warn "No GPIO write permission. May need to run as root or add user to gpio group."
            log_warn "  sudo usermod -aG gpio $USER"
        fi
    fi
}

check_permissions

PYTHONPATH="$PROJECT_ROOT" \
CE_A="$CE_A" CSN_A="$CSN_A" \
CE_B="$CE_B" CSN_B="$CSN_B" \
SCAN_INTERVAL="$SCAN_INTERVAL" \
NRF_LOG_FILE="$LOG_FILE" \
exec "$PYTHON" "$NRF_DIR/runtime.py" "$@"
