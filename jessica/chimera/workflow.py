"""CHAiMERA Workflow — high‑level workflow definitions that compose chains
for common security operations.

Provides pre‑built workflow templates (recon, full‑pentest, wireless‑audit,
etc.) that users can customise and feed into the chain engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jessica.chimera.chain import ChainStep, ChainType, ChimeraChainEngine, WorkflowChain

logger = logging.getLogger("jessica.chimera.workflow")


@dataclass
class WorkflowTemplate:
    """A reusable template that can generate a *WorkflowChain* with bound
    parameters."""

    name: str
    description: str = ""
    chain_type: ChainType = ChainType.SEQUENTIAL
    step_definitions: list[dict[str, Any]] = field(default_factory=list)

    def instantiate(self, target: str, overrides: dict[str, Any] | None = None) -> list[ChainStep]:
        """Create concrete *ChainStep* instances from the template."""
        steps: list[ChainStep] = []
        for defn in self.step_definitions:
            args = {**defn.get("args", {}), "target": target}
            if overrides:
                args.update(overrides)
            steps.append(
                ChainStep(
                    name=defn.get("name", ""),
                    tool=defn.get("tool", ""),
                    args=args,
                )
            )
        return steps


# ── pre‑built templates ──────────────────────────────────

RECON_TEMPLATE = WorkflowTemplate(
    name="full_recon",
    description="Full reconnaissance: passive OSINT → active port scan → service enumeration",
    chain_type=ChainType.SEQUENTIAL,
    step_definitions=[
        {"name": "dns_enum", "tool": "dnsrecon", "args": {"mode": "std"}},
        {"name": "subdomain_enum", "tool": "amass", "args": {"mode": "passive"}},
        {"name": "port_scan", "tool": "nmap", "args": {"flags": "-sV -sC --open -T4"}},
        {"name": "web_scan", "tool": "nikto", "args": {}},
    ],
)

FULL_PENTEST_TEMPLATE = WorkflowTemplate(
    name="full_pentest",
    description="End‑to‑end pentest: recon → vuln scan → exploit → post‑exploit",
    chain_type=ChainType.FAN_OUT_FAN_IN,
    step_definitions=[
        {"name": "recon", "tool": "nmap", "args": {"flags": "-sV -sC -A"}},
        {"name": "web_vuln", "tool": "nikto", "args": {}},
        {"name": "sqli_check", "tool": "sqlmap", "args": {"level": 3}},
        {"name": "exploit", "tool": "metasploit", "args": {"auto": True}},
        {"name": "post_exploit", "tool": "crackmapexec", "args": {}},
    ],
)

WIRELESS_AUDIT_TEMPLATE = WorkflowTemplate(
    name="wireless_audit",
    description="Wireless security audit using PineAP suite",
    chain_type=ChainType.SEQUENTIAL,
    step_definitions=[
        {"name": "wifi_scan", "tool": "airodump-ng", "args": {}},
        {"name": "deauth", "tool": "mdk4", "args": {"mode": "d"}},
        {"name": "handshake_capture", "tool": "aircrack-ng", "args": {}},
        {"name": "crack", "tool": "hashcat", "args": {"mode": 22000}},
    ],
)

NETWORK_SNIFF_TEMPLATE = WorkflowTemplate(
    name="network_sniff",
    description="Parallel MITM sniffing with ettercap + bettercap + wireshark",
    chain_type=ChainType.PARALLEL,
    step_definitions=[
        {"name": "arp_spoof", "tool": "ettercap", "args": {"mode": "mitm"}},
        {"name": "http_proxy", "tool": "bettercap", "args": {"caplet": "http-ui"}},
        {"name": "packet_capture", "tool": "tshark", "args": {"duration": 300}},
    ],
)

BUILTIN_TEMPLATES: dict[str, WorkflowTemplate] = {
    t.name: t
    for t in [RECON_TEMPLATE, FULL_PENTEST_TEMPLATE, WIRELESS_AUDIT_TEMPLATE, NETWORK_SNIFF_TEMPLATE]
}


class WorkflowManager:
    """Manages workflow templates and dispatches them to the chain engine."""

    def __init__(self, engine: ChimeraChainEngine) -> None:
        self._engine = engine
        self._templates: dict[str, WorkflowTemplate] = dict(BUILTIN_TEMPLATES)

    def register_template(self, template: WorkflowTemplate) -> None:
        self._templates[template.name] = template
        logger.info("Registered workflow template: %s", template.name)

    def list_templates(self) -> list[str]:
        return list(self._templates.keys())

    async def launch(self, template_name: str, target: str, overrides: dict[str, Any] | None = None) -> WorkflowChain:
        """Instantiate a template and execute it."""
        tmpl = self._templates.get(template_name)
        if tmpl is None:
            raise KeyError(f"Unknown workflow template: {template_name}")
        steps = tmpl.instantiate(target, overrides)
        chain = self._engine.create_chain(name=f"{template_name}@{target}", chain_type=tmpl.chain_type, steps=steps)
        return await self._engine.execute_chain(chain.id)
