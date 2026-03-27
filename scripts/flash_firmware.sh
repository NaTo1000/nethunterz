#!/usr/bin/env bash
# Flash NethunterZ ESP32 firmware using esptool.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FIRMWARE_DIR="$PROJECT_ROOT/firmware"

# ── Defaults ──────────────────────────────────────────────────────────────────
PORT="${ESP_PORT:-/dev/ttyUSB0}"
BAUD="${ESP_BAUD:-921600}"
CHIP="${ESP_CHIP:-esp32}"
FLASH_FREQ="${FLASH_FREQ:-80m}"
FLASH_MODE="${FLASH_MODE:-dio}"
FLASH_SIZE="${FLASH_SIZE:-detect}"
BUILD_DIR="$FIRMWARE_DIR/.pio/build/esp32"
FIRMWARE_BIN="$BUILD_DIR/firmware.bin"
BOOTLOADER_BIN="$BUILD_DIR/bootloader.bin"
PARTITIONS_BIN="$BUILD_DIR/partitions.bin"
FLASH_OFFSET_FW="0x10000"
FLASH_OFFSET_BL="0x1000"
FLASH_OFFSET_PT="0x8000"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Flash NethunterZ firmware to ESP32

Options:
  -p, --port PORT       Serial port (default: $PORT)
  -b, --baud BAUD       Upload baud rate (default: $BAUD)
  -c, --chip CHIP       Chip type: esp32/esp32s2/esp32s3/esp32c3 (default: $CHIP)
  -f, --firmware BIN    Firmware binary path
  -B, --build           Build firmware before flashing (requires PlatformIO)
  -e, --erase           Erase flash before flashing
  -m, --monitor         Open serial monitor after flashing
  -h, --help            Show this help

Environment variables:
  ESP_PORT, ESP_BAUD, ESP_CHIP
EOF
    exit 0
}

check_dependencies() {
    local missing=()
    command -v esptool.py &>/dev/null || missing+=("esptool.py")
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Install with: pip install esptool"
        exit 1
    fi
}

build_firmware() {
    log_info "Building firmware with PlatformIO..."
    command -v pio &>/dev/null || { log_error "PlatformIO (pio) not found"; exit 1; }
    cd "$FIRMWARE_DIR"
    pio run -e esp32
    log_info "Build complete"
}

erase_flash() {
    log_warn "Erasing flash on $PORT..."
    esptool.py --chip "$CHIP" --port "$PORT" --baud "$BAUD" erase_flash
    log_info "Flash erased"
}

flash_firmware() {
    local fw_bin="${1:-$FIRMWARE_BIN}"
    if [[ ! -f "$fw_bin" ]]; then
        log_error "Firmware binary not found: $fw_bin"
        log_info "Run with --build flag to compile first, or specify --firmware path"
        exit 1
    fi

    log_info "Flashing $CHIP on $PORT at $BAUD baud..."
    log_info "Firmware: $fw_bin"

    local esptool_args=(
        --chip "$CHIP"
        --port "$PORT"
        --baud "$BAUD"
        --before default_reset
        --after hard_reset
        write_flash
        -z
        --flash_freq "$FLASH_FREQ"
        --flash_mode "$FLASH_MODE"
        --flash_size "$FLASH_SIZE"
    )

    if [[ -f "$BOOTLOADER_BIN" ]]; then
        esptool_args+=("$FLASH_OFFSET_BL" "$BOOTLOADER_BIN")
        log_info "Including bootloader: $BOOTLOADER_BIN"
    fi
    if [[ -f "$PARTITIONS_BIN" ]]; then
        esptool_args+=("$FLASH_OFFSET_PT" "$PARTITIONS_BIN")
        log_info "Including partition table: $PARTITIONS_BIN"
    fi
    esptool_args+=("$FLASH_OFFSET_FW" "$fw_bin")

    esptool.py "${esptool_args[@]}"
    log_info "Flash successful!"
}

open_monitor() {
    log_info "Opening serial monitor ($PORT @ 115200)..."
    if command -v pio &>/dev/null; then
        pio device monitor --port "$PORT" --baud 115200
    elif command -v screen &>/dev/null; then
        screen "$PORT" 115200
    else
        log_warn "No serial monitor found. Install 'screen' or use PlatformIO."
    fi
}

# ── Parse arguments ───────────────────────────────────────────────────────────
DO_BUILD=false
DO_ERASE=false
DO_MONITOR=false
CUSTOM_FW=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)     PORT="$2"; shift 2 ;;
        -b|--baud)     BAUD="$2"; shift 2 ;;
        -c|--chip)     CHIP="$2"; shift 2 ;;
        -f|--firmware) CUSTOM_FW="$2"; shift 2 ;;
        -B|--build)    DO_BUILD=true; shift ;;
        -e|--erase)    DO_ERASE=true; shift ;;
        -m|--monitor)  DO_MONITOR=true; shift ;;
        -h|--help)     usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

log_info "NethunterZ ESP32 Flash Tool"
log_info "Chip: $CHIP | Port: $PORT | Baud: $BAUD"
check_dependencies
[[ "$DO_BUILD" == true ]] && build_firmware
[[ "$DO_ERASE" == true ]] && erase_flash
flash_firmware "${CUSTOM_FW}"
[[ "$DO_MONITOR" == true ]] && open_monitor
