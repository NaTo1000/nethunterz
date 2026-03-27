#!/bin/bash
# verify_firmware.sh - Verify GPG signatures of firmware files
# Usage: ./verify_firmware.sh <firmware_dir>

set -euo pipefail

FIRMWARE_DIR="${1:?Usage: $0 <firmware_dir>}"
STRICT="${STRICT:-false}"

if [ ! -d "$FIRMWARE_DIR" ]; then
    echo "ERROR: Firmware directory not found: $FIRMWARE_DIR" >&2
    exit 1
fi

echo "[+] Verifying firmware signatures in: $FIRMWARE_DIR"

if ! command -v gpg &>/dev/null; then
    echo "ERROR: gpg not found in PATH" >&2
    exit 1
fi

VERIFIED=0
FAILED=0
MISSING=0

for firmware_file in "$FIRMWARE_DIR"/*.bin; do
    [ -f "$firmware_file" ] || continue

    echo "[*] Verifying: $(basename "$firmware_file")"

    # Look for signature file
    sig_file=""
    for ext in ".sig" ".asc"; do
        if [ -f "${firmware_file}${ext}" ]; then
            sig_file="${firmware_file}${ext}"
            break
        fi
    done

    if [ -z "$sig_file" ]; then
        echo "    [!] No signature file found for: $(basename "$firmware_file")"
        MISSING=$((MISSING + 1))
        if [ "$STRICT" = "true" ]; then
            FAILED=$((FAILED + 1))
        fi
        continue
    fi

    if gpg --verify "$sig_file" "$firmware_file" 2>&1; then
        echo "    [+] Signature VALID: $(basename "$sig_file")"
        VERIFIED=$((VERIFIED + 1))
    else
        echo "    [-] Signature INVALID: $(basename "$sig_file")" >&2
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

# Verify checksums file if present
if [ -f "$FIRMWARE_DIR/checksums.txt" ]; then
    echo "[*] Verifying SHA256 checksums..."
    if (cd "$FIRMWARE_DIR" && sha256sum -c checksums.txt 2>&1); then
        echo "[+] All checksums match"
    else
        echo "[-] Checksum verification failed" >&2
        FAILED=$((FAILED + 1))
    fi
fi

echo ""
echo "[+] Verification summary: $VERIFIED verified, $FAILED failed, $MISSING missing signatures"

if [ "$FAILED" -gt 0 ]; then
    echo "[-] VERIFICATION FAILED" >&2
    exit 1
fi

echo "[+] All signatures valid"
exit 0
