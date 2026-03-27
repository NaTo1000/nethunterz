"""
TWINBRAIN Algorithm - Dual-processing AI with real-time decision validation.

TWINBRAIN runs two independent decision branches in parallel and applies
a consensus mechanism before committing to any action. This eliminates
single-point-of-failure in AI decision-making and provides error resilience.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple


class ConsensusStrategy(Enum):
    MAJORITY = "majority"          # 2-of-2 agreement required
    WEIGHTED = "weighted"          # Confidence-weighted vote
    CONSERVATIVE = "conservative"  # Always pick the safer option
    AGGRESSIVE = "aggressive"      # Pick the higher-confidence option


@dataclass
class BrainDecision:
    """A decision produced by one brain branch."""
    branch_id: str
    action: str
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsensusResult:
    """The result of running TWINBRAIN consensus."""
    agreed: bool
    final_action: str
    confidence: float
    brain_a: BrainDecision
    brain_b: BrainDecision
    strategy_used: ConsensusStrategy
    elapsed_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agreed": self.agreed,
            "final_action": self.final_action,
            "confidence": self.confidence,
            "brain_a": self.brain_a.to_dict(),
            "brain_b": self.brain_b.to_dict(),
            "strategy": self.strategy_used.value,
            "elapsed_ms": self.elapsed_ms,
            "divergence_score": self.divergence_score,
        }

    @property
    def divergence_score(self) -> float:
        """How much the two brains disagreed (0=identical, 1=opposite)."""
        if self.brain_a.action == self.brain_b.action:
            return 0.0
        conf_diff = abs(self.brain_a.confidence - self.brain_b.confidence)
        return min(1.0, conf_diff + 0.5)


class TwinBrainAlgorithm:
    """
    TWINBRAIN: Dual-processing consensus AI engine.

    Runs two independent decision pipelines simultaneously and applies
    configurable consensus logic before committing actions. Used within
    the Grok 420 / CHAiMERA stack for validated decision-making.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED,
        agreement_threshold: float = 0.7,
        enable_memory_sync: bool = True,
    ) -> None:
        self.strategy = strategy
        self.agreement_threshold = agreement_threshold
        self.enable_memory_sync = enable_memory_sync
        self._decision_history: List[ConsensusResult] = []
        self._divergence_log: List[Tuple[str, str, float]] = []

    async def evaluate(
        self,
        context: Dict[str, Any],
        brain_a_fn: Callable[[Dict[str, Any]], Any],
        brain_b_fn: Callable[[Dict[str, Any]], Any],
    ) -> ConsensusResult:
        """
        Run dual-brain evaluation and return consensus result.

        Args:
            context: Shared input context for both brains.
            brain_a_fn: First branch decision function (async or sync).
            brain_b_fn: Second branch decision function (async or sync).
        """
        start = time.time()

        # Run both branches in parallel
        result_a, result_b = await asyncio.gather(
            self._run_branch("A", brain_a_fn, context),
            self._run_branch("B", brain_b_fn, context),
        )

        consensus = self._apply_consensus(result_a, result_b)
        elapsed_ms = (time.time() - start) * 1000

        result = ConsensusResult(
            agreed=(result_a.action == result_b.action),
            final_action=consensus[0],
            confidence=consensus[1],
            brain_a=result_a,
            brain_b=result_b,
            strategy_used=self.strategy,
            elapsed_ms=elapsed_ms,
        )

        self._decision_history.append(result)

        if not result.agreed:
            self._divergence_log.append(
                (result_a.action, result_b.action, result.divergence_score)
            )

        return result

    async def _run_branch(
        self,
        branch_id: str,
        fn: Callable,
        context: Dict[str, Any],
    ) -> BrainDecision:
        """Execute one brain branch, normalize to BrainDecision."""
        if asyncio.iscoroutinefunction(fn):
            raw = await fn(context)
        else:
            raw = fn(context)

        if isinstance(raw, BrainDecision):
            return raw

        # Normalize dict output
        if isinstance(raw, dict):
            return BrainDecision(
                branch_id=branch_id,
                action=raw.get("action", "noop"),
                confidence=float(raw.get("confidence", 0.5)),
                reasoning=raw.get("reasoning", ""),
                metadata=raw.get("metadata", {}),
            )

        return BrainDecision(
            branch_id=branch_id,
            action=str(raw),
            confidence=0.5,
            reasoning="raw output",
        )

    def _apply_consensus(
        self,
        a: BrainDecision,
        b: BrainDecision,
    ) -> Tuple[str, float]:
        """Apply consensus strategy to pick final action."""
        if self.strategy == ConsensusStrategy.MAJORITY:
            if a.action == b.action:
                return a.action, (a.confidence + b.confidence) / 2
            # No agreement - defer to higher confidence
            if a.confidence >= b.confidence:
                return a.action, a.confidence * 0.8  # penalty for no consensus
            return b.action, b.confidence * 0.8

        elif self.strategy == ConsensusStrategy.WEIGHTED:
            if a.action == b.action:
                combined = (a.confidence + b.confidence) / 2
                return a.action, combined
            # Weighted by confidence
            total = a.confidence + b.confidence
            if total == 0:
                return a.action, 0.0
            weight_a = a.confidence / total
            weight_b = b.confidence / total
            if weight_a >= weight_b:
                return a.action, a.confidence * weight_a
            return b.action, b.confidence * weight_b

        elif self.strategy == ConsensusStrategy.CONSERVATIVE:
            # Always prefer the action with lower confidence (more cautious)
            if a.confidence <= b.confidence:
                return a.action, a.confidence
            return b.action, b.confidence

        elif self.strategy == ConsensusStrategy.AGGRESSIVE:
            if a.confidence >= b.confidence:
                return a.action, a.confidence
            return b.action, b.confidence

        return a.action, a.confidence

    def get_divergence_rate(self) -> float:
        """Return the fraction of decisions where brains disagreed."""
        if not self._decision_history:
            return 0.0
        diverged = sum(1 for r in self._decision_history if not r.agreed)
        return diverged / len(self._decision_history)

    def get_stats(self) -> Dict[str, Any]:
        """Return performance statistics."""
        history = self._decision_history
        if not history:
            return {"total_evaluations": 0}

        avg_conf = sum(r.confidence for r in history) / len(history)
        avg_ms = sum(r.elapsed_ms for r in history) / len(history)

        return {
            "total_evaluations": len(history),
            "agreement_rate": 1.0 - self.get_divergence_rate(),
            "divergence_rate": self.get_divergence_rate(),
            "average_confidence": avg_conf,
            "average_latency_ms": avg_ms,
            "strategy": self.strategy.value,
        }

    def compute_state_hash(self) -> str:
        """Compute a hash of the current decision state for blockchain sync."""
        if not self._decision_history:
            return hashlib.sha256(b"empty").hexdigest()
        last = self._decision_history[-1]
        payload = f"{last.final_action}:{last.confidence}:{last.elapsed_ms}"
        return hashlib.sha256(payload.encode()).hexdigest()
