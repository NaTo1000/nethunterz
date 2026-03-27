#!/system/bin/sh
# check_services.sh - Check which NetHunter services are currently running
#
# This script queries the status of common NetHunter services inside the
# Kali chroot and reports whether they are active.
#
# Usage: check_services.sh
#
# Services checked:
#   - SSH (sshd)
#   - Apache2 (apache2)
#   - MySQL / MariaDB (mysqld / mariadbd)
#   - Metasploit RPC (msfrpcd)
#   - Bluetooth (bluetoothd)
#   - OpenVPN (openvpn)
#   - BeEF (beef-xss)
#   - Kismet (kismet)
#
# Author: NetHunterZ

CHROOT="/data/local/nhsystem/kali-arm64"

###############################################################################
# Logging helpers
###############################################################################
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    local service="$1"
    local pid
    pid=$(pgrep -f "$service" 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        printf "  ${GREEN}[RUNNING]${NC}  %-20s (PID: %s)\n" "$service" "$pid"
    else
        printf "  ${RED}[STOPPED]${NC}  %-20s\n" "$service"
    fi
}

###############################################################################
# Main
###############################################################################
echo ""
echo "======================================"
echo "  NetHunterZ Service Status Check"
echo "======================================"
echo ""

# Core services
echo "-- Core Services --"
print_status "sshd"
print_status "apache2"
print_status "mysqld"
print_status "mariadbd"

echo ""
echo "-- Security Tools --"
print_status "msfrpcd"
print_status "beef-xss"
print_status "kismet"
print_status "bettercap"

echo ""
echo "-- Network Services --"
print_status "openvpn"
print_status "hostapd"
print_status "dnsmasq"
print_status "bluetoothd"

echo ""
echo "-- GPS Services --"
print_status "gpsd"

echo ""
echo "======================================"
echo "  Chroot Status"
echo "======================================"
if mountpoint -q "$CHROOT/proc" 2>/dev/null; then
    printf "  ${GREEN}[MOUNTED]${NC}  Kali chroot (%s)\n" "$CHROOT"
else
    printf "  ${RED}[NOT MOUNTED]${NC} Kali chroot (%s)\n" "$CHROOT"
fi
echo ""
