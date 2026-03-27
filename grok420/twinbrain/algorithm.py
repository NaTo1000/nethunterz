"""TWINBRAIN Algorithm — dual-brain consensus for validated AI decisions.

Two independent brain instances evaluate the same input concurrently.
A consensus mechanism then validates the final output against a
configurable agreement threshold.  Divergence triggers retry logic.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from grok420.config import TwinBrainConfig
from grok420.twinbrain.synchronizer import BrainSynchronizer

logger = logging.getLogger(__name__)


EvalFn = Callable[[Any], Coroutine[Any, Any, Any]]


@dataclass
class BrainOutput:
    """Output from one brain instance."""

    brain_id: str
    result: Any
    confidence: float = 1.0

    def to_state(self) -> dict[str, Any]:
        return {
            "brain_id": self.brain_id,
            "confidence": self.confidence,
            "result_type": type(self.result).__name__,
        }


@dataclass
class ConsensusResult:
    """Validated output from the TWINBRAIN consensus mechanism."""

    agreed: bool
    output: Any
    confidence: float
    brain_a: BrainOutput
    brain_b: BrainOutput
    retries: int = 0
    error: str | None = None


class BrainInstance:
    """A single AI brain that evaluates inputs via an injected eval function."""

    def __init__(self, brain_id: str, eval_fn: EvalFn) -> None:
        self.brain_id = brain_id
        self._eval_fn = eval_fn
        self._sync = BrainSynchronizer()

    async def start(self) -> None:
        await self._sync.start()

    async def stop(self) -> None:
        await self._sync.stop()

    async def evaluate(self, data: Any) -> BrainOutput:
        result = await self._eval_fn(data)
        confidence = self._extract_confidence(result)
        output = BrainOutput(
            brain_id=self.brain_id, result=result, confidence=confidence
        )
        await self._sync.send(self.brain_id, output.to_state())
        return output

    @staticmethod
    def _extract_confidence(result: Any) -> float:
        if isinstance(result, dict):
            return float(result.get("confidence", 1.0))
        return 1.0

    @property
    def synchronizer(self) -> BrainSynchronizer:
        return self._sync


class TwinBrain:
    """Multi-core AI synchronization with dual-brain consensus.

    Two :class:`BrainInstance` objects (A and B) independently evaluate
    each input.  The consensus mechanism compares outputs and, if they
    agree within *consensus_threshold*, returns the averaged result.
    Divergent outputs trigger up to *max_divergence_retries* re-evaluations.
    """

    def __init__(
        self,
        eval_fn_a: EvalFn,
        eval_fn_b: EvalFn | None = None,
        config: TwinBrainConfig | None = None,
    ) -> None:
        self._config = config or TwinBrainConfig()
        self._brain_a = BrainInstance("brain_a", eval_fn_a)
        self._brain_b = BrainInstance(
            "brain_b", eval_fn_b if eval_fn_b is not None else eval_fn_a
        )
        # Wire synchronizers for in-process state sharing
        self._brain_a.synchronizer.connect_to(self._brain_b.synchronizer)
        self._brain_b.synchronizer.connect_to(self._brain_a.synchronizer)
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        await self._brain_a.start()
        await self._brain_b.start()
        self._running = True
        logger.info("TwinBrain started (threshold=%.2f)", self._config.consensus_threshold)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._brain_a.stop()
        await self._brain_b.stop()
        logger.info("TwinBrain stopped")

    async def __aenter__(self) -> "TwinBrain":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Consensus evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, data: Any) -> ConsensusResult:
        """Run both brains and apply consensus logic."""
        if not self._running:
            raise RuntimeError("TwinBrain.start() must be called first")

        retries = 0
        error: str | None = None

        for attempt in range(self._config.max_divergence_retries + 1):
            retries = attempt
            try:
                out_a, out_b = await asyncio.gather(
                    self._brain_a.evaluate(data),
                    self._brain_b.evaluate(data),
                )
                agreed, confidence, fused = self._consensus(out_a, out_b)
                if agreed:
                    return ConsensusResult(
                        agreed=True,
                        output=fused,
                        confidence=confidence,
                        brain_a=out_a,
                        brain_b=out_b,
                        retries=retries,
                    )
                logger.warning(
                    "Brain divergence on attempt %d (confidence=%.2f)",
                    attempt,
                    confidence,
                )
            except Exception as exc:
                error = str(exc)
                logger.error("TwinBrain evaluation error: %s", exc)

        # Return best-effort result after exhausting retries
        try:
            out_a_f, out_b_f = await asyncio.gather(
                self._brain_a.evaluate(data),
                self._brain_b.evaluate(data),
            )
            _, conf, fused = self._consensus(out_a_f, out_b_f)
            return ConsensusResult(
                agreed=False,
                output=fused,
                confidence=conf,
                brain_a=out_a_f,
                brain_b=out_b_f,
                retries=retries,
                error=error or "max_retries_exceeded",
            )
        except Exception as exc:
            # Return empty fallback
            empty = BrainOutput(brain_id="fallback", result=None, confidence=0.0)
            return ConsensusResult(
                agreed=False,
                output=None,
                confidence=0.0,
                brain_a=empty,
                brain_b=empty,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _consensus(
        self, a: BrainOutput, b: BrainOutput
    ) -> tuple[bool, float, Any]:
        """Determine if brains agree and produce fused output."""
        avg_confidence = (a.confidence + b.confidence) / 2.0
        if avg_confidence >= self._config.consensus_threshold:
            # Prefer higher-confidence output
            fused = a.result if a.confidence >= b.confidence else b.result
            return True, avg_confidence, fused
        return False, avg_confidence, a.result

    # ------------------------------------------------------------------
    # Parameter controls
    # ------------------------------------------------------------------

    def set_consensus_threshold(self, threshold: float) -> None:
        if not 0.5 <= threshold <= 1.0:
            raise ValueError("threshold must be 0.5–1.0")
        self._config.consensus_threshold = threshold
        logger.info("Consensus threshold set to %.2f", threshold)

    def set_sync_interval(self, interval_ms: int) -> None:
        if interval_ms < 10:
            raise ValueError("sync_interval_ms must be >= 10")
        self._config.sync_interval_ms = interval_ms
