# iFINITEAi2025JESSICAi — Huntress Edition
# Full Kali + BlackArch security suite with CHAiMERA orchestration
FROM kalilinux/kali-rolling:latest AS base

LABEL maintainer="NaTo1000"
LABEL description="iFINITEAi2025JESSICAi Huntress Edition — Autonomous Security Platform"
LABEL version="2025.1.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV JESSICA_HOME=/opt/jessica
ENV PYTHONUNBUFFERED=1

# ──────────────────────────────────────────────
# Stage 1: Kali full security suite
# ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core Kali meta-packages
    kali-linux-headless \
    kali-tools-information-gathering \
    kali-tools-vulnerability \
    kali-tools-web \
    kali-tools-exploitation \
    kali-tools-sniffing-spoofing \
    kali-tools-wireless \
    kali-tools-passwords \
    kali-tools-post-exploitation \
    kali-tools-forensics \
    # Individual critical tools
    nmap \
    wireshark-common \
    tshark \
    metasploit-framework \
    nikto \
    ettercap-text-only \
    ettercap-common \
    arpwatch \
    arping \
    aircrack-ng \
    hostapd \
    dnsmasq \
    macchanger \
    reaver \
    bettercap \
    sqlmap \
    john \
    hashcat \
    hydra \
    gobuster \
    dirb \
    wfuzz \
    burpsuite \
    zaproxy \
    # Network & monitoring
    net-tools \
    iproute2 \
    iptables \
    nftables \
    tcpdump \
    netcat-openbsd \
    socat \
    proxychains4 \
    tor \
    # USB & driver support
    usbutils \
    usb-modeswitch \
    firmware-linux \
    firmware-atheros \
    firmware-realtek \
    firmware-iwlwifi \
    firmware-misc-nonfree \
    # Python & build tools
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────
# Stage 2: BlackArch repository tools
# ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # BlackArch-equivalent tools available in Kali
    responder \
    crackmapexec \
    evil-winrm \
    bloodhound \
    impacket-scripts \
    seclists \
    wordlists \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────
# Stage 3: WiFi Pineapple suite components
# ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    hostapd-wpe \
    mdk4 \
    wifite \
    fluxion \
    && rm -rf /var/lib/apt/lists/* || true

# ──────────────────────────────────────────────
# Stage 4: JESSICA platform installation
# ──────────────────────────────────────────────
WORKDIR ${JESSICA_HOME}

COPY pyproject.toml .
COPY jessica/ jessica/
COPY configs/ configs/

RUN python3 -m pip install --break-system-packages --no-cache-dir -e ".[ai]" || \
    python3 -m pip install --no-cache-dir -e ".[ai]"

# ──────────────────────────────────────────────
# Port exposure for monitored services
# ──────────────────────────────────────────────
# ConductorX API
EXPOSE 9000
# CHAiMERA workflow engine
EXPOSE 9001
# Monitoring dashboard
EXPOSE 9002
# Proxy / intercept
EXPOSE 8080
# DNS
EXPOSE 53/udp
# DHCP
EXPOSE 67/udp

ENTRYPOINT ["jessica"]
CMD ["--mode", "autonomous", "--orchestration", "conductorx"]
