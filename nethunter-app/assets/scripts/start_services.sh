#!/bin/sh
# start_services.sh – start all NetHunter services inside the chroot
CHROOT_DIR="${NH_CHROOT_DIR:-/data/local/nhsystem/kali-arm64}"

log() { echo "[$(date +%T)] $*"; }

# Check chroot is mounted
if ! mountpoint -q "$CHROOT_DIR/proc" 2>/dev/null; then
    log "ERROR: Chroot is not mounted. Run bootkali first."
    exit 1
fi

log "Starting services inside chroot..."

# Run init.d scripts
chroot "$CHROOT_DIR" /bin/sh -c "
    for script in /etc/init.d/[0-9]*; do
        [ -x "\$script" ] && "\$script" start
    done
" && log "Init.d scripts executed"

log "All services started"
exit 0
