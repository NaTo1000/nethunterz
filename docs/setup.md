# iFINITEAi2025JESSICAi — Setup Guide

## Prerequisites

- **Python 3.11+**
- **Docker** and **Docker Compose** (for full deployment)
- **Linux** (Kali or Debian-based recommended)
- **Root/sudo** for network operations and monitor mode

## Quick Start (Development)

```bash
# Clone the repository
git clone https://github.com/NaTo1000/nethunterz.git
cd nethunterz

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Launch the CLI
jessica --help
```

## Docker Deployment (Full Stack)

```bash
# Set your Hugging Face token (optional, for AI features)
export HF_TOKEN="hf_your_token_here"

# Build and launch the full stack
docker-compose up -d

# Check status
docker-compose ps
jessica health --component all
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| `conductorx` | 9000 | ConductorX API — cluster orchestrator |
| `chimera` | 9001 | CHAiMERA workflow engine |
| `orchestrator-worker` | — | Scalable worker pool (3 replicas default) |
| `monitor` | — | Autonomous entry-point monitor |
| `ai-transformer` | — | AI transformer bot layer |

## CLI Commands

```bash
# Full autonomous mode (default)
jessica --mode autonomous

# Conductor-only mode
jessica --mode conductor --bind 0.0.0.0:9000

# Quick network scan
jessica scan --target 192.168.1.0/24

# Full scan with service + OS detection
jessica scan --target 10.0.0.1 --full

# Launch a workflow template
jessica workflow --template full_recon --target example.com
jessica workflow --template wireless_audit --target wlan0

# List installed tool suites
jessica suites

# List network interfaces
jessica interfaces

# Health check
jessica health --component conductorx
```

## Workflow Templates

| Template | Description | Chain Type |
|----------|-------------|------------|
| `full_recon` | DNS → subdomains → port scan → web scan | Sequential |
| `full_pentest` | Recon → vuln scan → exploit → post-exploit | Fan-out/Fan-in |
| `wireless_audit` | WiFi scan → deauth → handshake → crack | Sequential |
| `network_sniff` | ARP spoof + HTTP proxy + packet capture | Parallel |

## Configuration

All configuration is in YAML files under `configs/`:

- `kali-suite.yml` — Kali Linux tool definitions
- `blackarch-suite.yml` — BlackArch extended tools
- `pineap-suite.yml` — WiFi Pineapple suite
- `orchestration.yml` — CHAiMERA + ConductorX + monitoring + AI settings

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JESSICA_HOME` | project root | Base directory |
| `JESSICA_MODE` | `autonomous` | Runtime mode |
| `HF_TOKEN` | — | Hugging Face API token |
| `HF_MODEL` | — | Default HF model override |
| `CHIMERA_STACK_DEPTH` | `3` | Stack overlay depth |
| `CHIMERA_STACK_WIDTH` | `3` | Stack overlay width |
| `CHIMERA_STACK_LAYERS` | `3` | Stack overlay height |
| `CONDUCTORX_CLUSTER` | `true` | Enable cluster mode |
| `CONDUCTORX_REPLICAS` | `3` | Cluster replica count |

## AI Integration

JESSICA integrates with Hugging Face for intelligent analysis:

```bash
# Set your token
export HF_TOKEN="hf_..."

# Launch with AI
jessica --mode ai

# Or configure in orchestration.yml:
# ai_integration:
#   huggingface:
#     enabled: true
#     default_models:
#       text_generation: "meta-llama/Llama-3.1-70B-Instruct"
```

### Transformer Bot Roles

- **Classifier** — categorise scan results
- **Analyser** — summarise findings
- **Planner** — generate adaptive attack plans
- **Scorer** — rate vulnerabilities by severity
