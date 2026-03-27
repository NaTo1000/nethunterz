#!/bin/bash
# sign_firmware.sh - GPG sign firmware files for distribution
# Usage: ./sign_firmware.sh <firmware_dir> [gpg_passphrase]

set -euo pipefail

FIRMWARE_DIR="${1:?Usage: $0 <firmware_dir> [passphrase]}"
GPG_PASSPHRASE="${2:-}"

if [ ! -d "$FIRMWARE_DIR" ]; then
    echo "ERROR: Firmware directory not found: $FIRMWARE_DIR" >&2
    exit 1
fi

echo "[+] Signing firmware files in: $FIRMWARE_DIR"

# Check if GPG is available
if ! command -v gpg &>/dev/null; then
    echo "ERROR: gpg not found in PATH" >&2
    exit 1
fi

SIGNED=0
FAILED=0

for firmware_file in "$FIRMWARE_DIR"/*.bin; do
    [ -f "$firmware_file" ] || continue

    sig_file="${firmware_file}.sig"
    echo "[*] Signing: $(basename "$firmware_file")"

    if [ -n "$GPG_PASSPHRASE" ]; then
        # Non-interactive signing with passphrase
        if echo "$GPG_PASSPHRASE" | gpg \
            --batch \
            --yes \
            --passphrase-fd 0 \
            --armor \
            --detach-sign \
            --output "$sig_file" \
            "$firmware_file" 2>/dev/null; then
            echo "    [+] Signature created: $(basename "$sig_file")"
            SIGNED=$((SIGNED + 1))
        else
            echo "    [-] Failed to sign: $(basename "$firmware_file")" >&2
            FAILED=$((FAILED + 1))
        fi
    else
        # Interactive / agent-based signing
        if gpg \
            --armor \
            --detach-sign \
            --output "$sig_file" \
            "$firmware_file"; then
            echo "    [+] Signature created: $(basename "$sig_file")"
            SIGNED=$((SIGNED + 1))
        else
            echo "    [-] Failed to sign: $(basename "$firmware_file")" >&2
            FAILED=$((FAILED + 1))
        fi
    fi
done

echo ""
echo "[+] Signing complete: $SIGNED signed, $FAILED failed"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi

# Create a combined checksums file
if [ -d "$FIRMWARE_DIR" ]; then
    echo ""
    echo "[+] Generating checksums file..."
    (cd "$FIRMWARE_DIR" && sha256sum *.bin *.sig 2>/dev/null) > "$FIRMWARE_DIR/checksums.txt" || true
    echo "[+] Checksums saved to: $FIRMWARE_DIR/checksums.txt"
fi

exit 0
