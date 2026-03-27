"""Decision Engine — multiplexed decision-making for complex AI tasks."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from grok420.config import DecisionMode

logger = logging.getLogger(__name__)


class DecisionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DecisionContext:
    """Input context for a decision request."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = field(default_factory=dict)
    mode: DecisionMode = DecisionMode.ADAPTIVE
    created_at: float = field(default_factory=time.monotonic)
    priority: int = 5  # 1 (highest) – 10 (lowest)


@dataclass
class DecisionResult:
    """Output of a completed decision pipeline."""

    decision_id: str
    status: DecisionStatus
    output: Any = None
    confidence: float = 0.0
    latency_s: float = 0.0
    pipeline: str = ""
    error: str | None = None


class DecisionEngine:
    """Multiplexed decision-making engine.

    Supports three modes:
    * **precision** — single deep pipeline, maximum accuracy.
    * **fusion** — multiple parallel shallow pipelines, results fused.
    * **adaptive** — automatically selects based on payload complexity.
    """

    def __init__(self, mode: DecisionMode = DecisionMode.ADAPTIVE) -> None:
        self._mode = mode
        self._history: list[DecisionResult] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(self, ctx: DecisionContext) -> DecisionResult:
        """Execute the decision pipeline for *ctx*."""
        start = time.monotonic()
        effective_mode = self._resolve_mode(ctx)
        try:
            if effective_mode == DecisionMode.PRECISION:
                output, conf, pipeline = await self._precision_pipeline(ctx)
            elif effective_mode == DecisionMode.FUSION:
                output, conf, pipeline = await self._fusion_pipeline(ctx)
            else:
                output, conf, pipeline = await self._adaptive_pipeline(ctx)

            result = DecisionResult(
                decision_id=ctx.decision_id,
                status=DecisionStatus.COMPLETED,
                output=output,
                confidence=conf,
                latency_s=time.monotonic() - start,
                pipeline=pipeline,
            )
        except Exception as exc:
            logger.error("Decision %s failed: %s", ctx.decision_id, exc)
            result = DecisionResult(
                decision_id=ctx.decision_id,
                status=DecisionStatus.FAILED,
                latency_s=time.monotonic() - start,
                error=str(exc),
            )

        async with self._lock:
            self._history.append(result)
        return result

    # ------------------------------------------------------------------
    # Pipeline implementations
    # ------------------------------------------------------------------

    async def _precision_pipeline(
        self, ctx: DecisionContext
    ) -> tuple[Any, float, str]:
        """Single deep evaluation — high accuracy, higher latency."""
        await asyncio.sleep(0)  # yield to event loop
        score = self._score_payload(ctx.payload)
        return {"decision": "precision", "score": score}, min(score, 1.0), "precision"

    async def _fusion_pipeline(
        self, ctx: DecisionContext
    ) -> tuple[Any, float, str]:
        """Parallel shallow pipelines, fused into a single result."""
        coros = [
            self._sub_pipeline(ctx, i) for i in range(3)
        ]
        sub_results = await asyncio.gather(*coros)
        fused_score = sum(r["score"] for r in sub_results) / len(sub_results)
        confidence = 1.0 - (
            max(r["score"] for r in sub_results)
            - min(r["score"] for r in sub_results)
        )
        return {
            "decision": "fusion",
            "fused_score": fused_score,
            "sub_results": sub_results,
        }, max(0.0, confidence), "fusion"

    async def _adaptive_pipeline(
        self, ctx: DecisionContext
    ) -> tuple[Any, float, str]:
        """Choose precision vs fusion based on payload complexity."""
        complexity = len(ctx.payload)
        if complexity > 10:
            return await self._fusion_pipeline(ctx)
        return await self._precision_pipeline(ctx)

    async def _sub_pipeline(
        self, ctx: DecisionContext, index: int
    ) -> dict[str, Any]:
        await asyncio.sleep(0)
        score = self._score_payload(ctx.payload) * (0.9 + index * 0.05)
        return {"pipeline_index": index, "score": min(score, 1.0)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_mode(self, ctx: DecisionContext) -> DecisionMode:
        return ctx.mode if ctx.mode != DecisionMode.ADAPTIVE else self._mode

    @staticmethod
    def _score_payload(payload: dict[str, Any]) -> float:
        """Deterministic score based on payload hash for testing."""
        import hashlib
        raw = str(sorted(payload.items())).encode()
        digest = hashlib.sha256(raw).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def decision_history(self) -> list[DecisionResult]:
        return list(self._history)

    def set_mode(self, mode: DecisionMode) -> None:
        self._mode = mode
        logger.info("DecisionEngine mode set to %s", mode)
