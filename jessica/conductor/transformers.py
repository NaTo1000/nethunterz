"""Transformer Bots — AI‑powered task classification, result analysis, and
adaptive planning agents that operate within the ConductorX pipeline.

Each transformer bot wraps a Hugging Face model and provides a typed
interface that the orchestrator can call to make intelligent routing and
analysis decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jessica.conductor.transformers")


class BotRole(str, Enum):
    """Roles that transformer bots can fulfil."""

    CLASSIFIER = "classifier"
    ANALYSER = "analyser"
    PLANNER = "planner"
    SCORER = "scorer"


@dataclass
class BotConfig:
    role: BotRole
    model_id: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


class TransformerBot:
    """A single transformer bot backed by a Hugging Face model.

    The bot exposes a simple ``run(input_data) → output`` interface.
    The actual model loading and inference is delegated to the
    :class:`jessica.ai.huggingface.HuggingFaceLayer`.
    """

    def __init__(self, config: BotConfig, hf_layer: Any = None) -> None:
        self._cfg = config
        self._hf = hf_layer
        self._ready = False

    @property
    def role(self) -> BotRole:
        return self._cfg.role

    @property
    def model_id(self) -> str:
        return self._cfg.model_id

    async def initialise(self) -> None:
        """Pre‑load the model via the HuggingFace layer."""
        if self._hf and hasattr(self._hf, "load_model"):
            await self._hf.load_model(self._cfg.model_id)
        self._ready = True
        logger.info("TransformerBot [%s] ready — model=%s", self.role.value, self.model_id)

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the bot's role‑specific logic."""
        if not self._ready:
            await self.initialise()

        if self.role == BotRole.CLASSIFIER:
            return await self._classify(input_data)
        if self.role == BotRole.ANALYSER:
            return await self._analyse(input_data)
        if self.role == BotRole.PLANNER:
            return await self._plan(input_data)
        if self.role == BotRole.SCORER:
            return await self._score(input_data)
        return {"error": f"Unknown role: {self.role}"}

    # ── role implementations ──────────────────────────────

    async def _classify(self, data: dict[str, Any]) -> dict[str, Any]:
        """Classify a task or result into a category using zero‑shot classification."""
        text = data.get("text", "")
        labels = data.get("labels", ["reconnaissance", "exploitation", "post_exploitation", "wireless"])
        if self._hf and hasattr(self._hf, "classify"):
            result = await self._hf.classify(text, labels, model_id=self.model_id)
            return {"classification": result}
        # Fallback stub
        return {"classification": {"label": labels[0], "score": 0.0}}

    async def _analyse(self, data: dict[str, Any]) -> dict[str, Any]:
        """Analyse tool output for key findings."""
        text = data.get("text", "")
        if self._hf and hasattr(self._hf, "generate"):
            prompt = f"Analyse the following security scan output and list key findings:\n\n{text}"
            result = await self._hf.generate(prompt, model_id=self.model_id)
            return {"analysis": result}
        return {"analysis": "No HF layer available — raw output returned", "raw": text}

    async def _plan(self, data: dict[str, Any]) -> dict[str, Any]:
        """Generate an adaptive attack/audit plan based on current findings."""
        findings = data.get("findings", [])
        if self._hf and hasattr(self._hf, "generate"):
            prompt = (
                "Based on the following findings, create a step-by-step penetration testing plan:\n"
                + "\n".join(f"- {f}" for f in findings)
            )
            result = await self._hf.generate(prompt, model_id=self.model_id)
            return {"plan": result}
        return {"plan": "No HF layer — manual planning required", "findings": findings}

    async def _score(self, data: dict[str, Any]) -> dict[str, Any]:
        """Score a finding on severity / exploitability."""
        finding = data.get("finding", "")
        if self._hf and hasattr(self._hf, "classify"):
            labels = ["critical", "high", "medium", "low", "informational"]
            result = await self._hf.classify(finding, labels, model_id=self.model_id)
            return {"threat_score": result}
        return {"threat_score": {"label": "medium", "score": 0.0}}


class TransformerBotPool:
    """Manages a pool of transformer bots, one per role.  Bots are created
    on demand and can be hot‑swapped with different models."""

    def __init__(self, hf_layer: Any = None) -> None:
        self._hf = hf_layer
        self._bots: dict[BotRole, TransformerBot] = {}

    def add_bot(self, config: BotConfig) -> TransformerBot:
        bot = TransformerBot(config, self._hf)
        self._bots[config.role] = bot
        return bot

    def get_bot(self, role: BotRole) -> TransformerBot | None:
        return self._bots.get(role)

    async def run(self, role: BotRole, input_data: dict[str, Any]) -> dict[str, Any]:
        bot = self._bots.get(role)
        if bot is None:
            raise KeyError(f"No bot registered for role: {role.value}")
        return await bot.run(input_data)

    def list_bots(self) -> list[dict[str, str]]:
        return [{"role": r.value, "model": b.model_id} for r, b in self._bots.items()]
