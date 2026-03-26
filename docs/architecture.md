# iFINITEAi2025JESSICAi — Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    iFINITEAi2025JESSICAi                     │
│                      Huntress Edition                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │   CLI / API   │   │   AI Layer   │   │    Monitoring    │ │
│  │  (click/rich) │   │ (HuggingFace)│   │  (Autonomous)   │ │
│  └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘ │
│         │                  │                     │           │
│  ┌──────▼──────────────────▼─────────────────────▼─────────┐ │
│  │              ConductorX — Super Orchestrator             │ │
│  │          (Raft Consensus · Adaptive Scheduling)          │ │
│  │    ┌─────────┐  ┌─────────┐  ┌─────────┐               │ │
│  │    │Worker #1│  │Worker #2│  │Worker #N│  (auto-scale)  │ │
│  │    └─────────┘  └─────────┘  └─────────┘               │ │
│  └──────────────────────┬──────────────────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────────┐ │
│  │           CHAiMERA — Chained Workflow Engine             │ │
│  │                                                          │ │
│  │  ┌─────────────── 3×3×3 Stack Overlay ────────────────┐ │ │
│  │  │                                                     │ │ │
│  │  │  Layer 0: Recon       Layer 1: Exploit    Layer 2:  │ │ │
│  │  │  ┌───┬───┬───┐      ┌───┬───┬───┐      Post-Expl  │ │ │
│  │  │  │ P │ A │ W │      │ W │ N │ W │      ┌───┬───┬──┐│ │ │
│  │  │  │ a │ c │ i │      │ e │ e │ i │      │ P │ L │ D ││ │ │
│  │  │  │ s │ t │ r │      │ b │ t │ r │      │ r │ a │ a ││ │ │
│  │  │  │ s │ i │ e │      │   │   │ e │      │ i │ t │ t ││ │ │
│  │  │  │ i │ v │ l │      │   │   │ l │      │ v │   │ a ││ │ │
│  │  │  │ v │ e │ e │      │   │   │ e │      │   │ M │   ││ │ │
│  │  │  │ e │   │ s │      │   │   │ s │      │ E │ o │ E ││ │ │
│  │  │  │   │   │ s │      │   │   │ s │      │ s │ v │ x ││ │ │
│  │  │  │   │   │   │      │   │   │   │      │ c │ e │ f ││ │ │
│  │  │  └───┴───┴───┘      └───┴───┴───┘      └───┴───┴──┘│ │ │
│  │  │   3 lanes × 3 stages per layer (input→proc→output)  │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────────┐ │
│  │                  Security Tool Suites                    │ │
│  │  ┌──────────┐  ┌────────────┐  ┌───────────────────┐   │ │
│  │  │ Kali     │  │ BlackArch  │  │ PineAP Suite      │   │ │
│  │  │ Suite    │  │ Suite      │  │ (WiFi Pineapple)  │   │ │
│  │  │          │  │            │  │                   │   │ │
│  │  │ nmap     │  │ bloodhound │  │ karma/mana        │   │ │
│  │  │ wireshark│  │ responder  │  │ evil twin         │   │ │
│  │  │ msfcon   │  │ amass      │  │ deauth            │   │ │
│  │  │ nikto    │  │ ghidra     │  │ probe harvest     │   │ │
│  │  │ ettercap │  │ radare2    │  │ captive portal    │   │ │
│  │  │ hydra    │  │ chisel     │  │ handshake capture │   │ │
│  │  │ ...30+   │  │ ...15+    │  │                   │   │ │
│  │  └──────────┘  └────────────┘  └───────────────────┘   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │            Autonomous Monitoring Layer                    │ │
│  │  Ports · Localhost · USB (A/C) · WiFi · Drivers · NICs   │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### ConductorX — Clustered Super Orchestrator
- **Raft consensus** cluster for high availability
- **Adaptive scheduling** with priority queues
- **Auto-scaling** workers based on queue depth (3→50 replicas)
- Task dispatch with least-loaded / round-robin / priority strategies

### CHAiMERA — Chained Workflow Engine
- **Chain types**: sequential, parallel, conditional, loop, fan-out/fan-in
- **Hot-swap**: switch between parallel ↔ series execution at runtime
- **3×3×3 Stack Overlay**: 27-cell execution grid (depth × width × height)
- Up to 27 concurrent workflow chains

### Transformer Bots (AI)
- **Classifier**: categorise tasks / results using zero-shot classification
- **Analyser**: summarise tool output for key findings
- **Planner**: generate adaptive attack plans
- **Scorer**: rate findings by severity / exploitability
- All powered by Hugging Face models with full placement control

### Autonomous Monitor
- Continuous scanning of all system entry points
- USB device insertion / removal detection (USB-A + USB-C)
- WiFi network and interface monitoring
- Port / service change detection
- Kernel module / driver watch
- Events feed into ConductorX for reactive orchestration

### Security Suites
| Suite | Tools | Categories |
|-------|-------|------------|
| **Kali** | 30+ | Recon, vuln analysis, exploitation, sniffing, wireless, passwords, web, post-exploit, forensics |
| **BlackArch** | 15+ | Extended recon, exploitation, RE, crypto, stego, social engineering, networking |
| **PineAP** | Full | Rogue AP, KARMA/MANA, probe harvest, evil twin, deauth, captive portal |
