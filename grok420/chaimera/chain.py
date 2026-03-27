"""CHAiMERA Chain — AI-on-AI layering with parallel/series/hybrid switching.

Each layer in the chain is an independent AI processing unit that can
consume the output of previous layers and produce enriched results.
The chain supports runtime switching between parallel, series, and hybrid
execution modes.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from grok420.chaimera.speed_modes import SpeedController
from grok420.chaimera.superconductor import Superconductor
from grok420.config import CHAiMERAConfig, ChainMode, SpeedMode

logger = logging.getLogger(__name__)


LayerFn = Callable[[Any], Coroutine[Any, Any, Any]]


@dataclass
class LayerResult:
    """Result produced by a single CHAiMERA layer."""

    layer_index: int
    output: Any
    confidence: float
    latency_ms: float
    layer_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class ChainResult:
    """Aggregated result from an entire CHAiMERA chain execution."""

    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: ChainMode = ChainMode.HYBRID
    speed_mode: SpeedMode = SpeedMode.BALANCED
    layer_results: list[LayerResult] = field(default_factory=list)
    final_output: Any = None
    total_latency_ms: float = 0.0
    success: bool = True
    error: str | None = None


class AILayer:
    """A single processing layer in the CHAiMERA chain.

    Wraps an arbitrary async coroutine factory and tracks per-layer
    performance metrics.  Each layer dynamically learns by tracking
    the average confidence of its outputs.
    """

    def __init__(self, index: int, fn: LayerFn) -> None:
        self.index = index
        self._fn = fn
        self._call_count = 0
        self._confidence_sum = 0.0

    @property
    def avg_confidence(self) -> float:
        if self._call_count == 0:
            return 0.0
        return self._confidence_sum / self._call_count

    async def process(self, data: Any) -> LayerResult:
        start = time.monotonic()
        output = await self._fn(data)
        latency_ms = (time.monotonic() - start) * 1000.0

        # Confidence heuristic — real systems embed this in the model output
        confidence = self._estimate_confidence(output)
        self._call_count += 1
        self._confidence_sum += confidence

        return LayerResult(
            layer_index=self.index,
            output=output,
            confidence=confidence,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _estimate_confidence(output: Any) -> float:
        """Extract confidence from dict output or fall back to 1.0."""
        if isinstance(output, dict):
            return float(output.get("confidence", 1.0))
        return 1.0


class CHAiMERAChain:
    """Three-speed, three-mode AI chain with superconductor orchestration.

    Modes
    -----
    * **parallel** — all layers run concurrently; redundant results are fused.
    * **series**   — layers run sequentially; each receives previous output.
    * **hybrid**   — series within speed-mode layer limit, parallel otherwise.
    """

    def __init__(self, config: CHAiMERAConfig | None = None) -> None:
        self._config = config or CHAiMERAConfig()
        self._layers: list[AILayer] = []
        self._speed = SpeedController(self._config.speed_mode)
        self._superconductor = Superconductor(self._config)
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        await self._superconductor.start()
        self._running = True
        logger.info(
            "CHAiMERAChain started: layers=%d mode=%s speed=%s",
            len(self._layers),
            self._config.chain_mode.value,
            self._config.speed_mode.value,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._superconductor.stop()
        logger.info("CHAiMERAChain stopped")

    async def __aenter__(self) -> "CHAiMERAChain":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def add_layer(self, fn: LayerFn) -> "CHAiMERAChain":
        """Append an AI layer function to the chain (fluent API)."""
        if len(self._layers) >= self._config.layer_count:
            raise ValueError(
                f"Layer limit reached ({self._config.layer_count}). "
                "Increase CHAiMERAConfig.layer_count."
            )
        self._layers.append(AILayer(index=len(self._layers), fn=fn))
        return self

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self, data: Any) -> ChainResult:
        """Execute the chain against *data* according to current mode."""
        if not self._running:
            raise RuntimeError("CHAiMERAChain.start() must be called first")

        mode = self._config.chain_mode
        start = time.monotonic()
        result = ChainResult(mode=mode, speed_mode=self._config.speed_mode)

        try:
            if mode == ChainMode.PARALLEL:
                result.layer_results = await self._run_parallel(data)
                result.final_output = self._fuse(result.layer_results)
            elif mode == ChainMode.SERIES:
                result.layer_results, result.final_output = await self._run_series(data)
            else:
                result.layer_results, result.final_output = await self._run_hybrid(data)
        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.error("CHAiMERAChain run failed: %s", exc)

        result.total_latency_ms = (time.monotonic() - start) * 1000.0
        return result

    # ------------------------------------------------------------------
    # Mode implementations
    # ------------------------------------------------------------------

    async def _run_parallel(self, data: Any) -> list[LayerResult]:
        coros = [
            self._superconductor.execute(lambda l=layer: l.process(data))
            for layer in self._layers
        ]
        return list(await asyncio.gather(*coros))

    async def _run_series(
        self, data: Any
    ) -> tuple[list[LayerResult], Any]:
        results: list[LayerResult] = []
        current = data
        for layer in self._layers:
            lr = await self._superconductor.execute(
                lambda l=layer, d=current: l.process(d)
            )
            results.append(lr)
            current = lr.output
        return results, current

    async def _run_hybrid(
        self, data: Any
    ) -> tuple[list[LayerResult], Any]:
        """Series up to speed-mode layer limit, parallel for the rest."""
        serial_limit = self._speed.profile.max_layers
        serial_layers = self._layers[:serial_limit]
        parallel_layers = self._layers[serial_limit:]

        all_results: list[LayerResult] = []
        current = data

        # Serial phase
        for layer in serial_layers:
            lr = await self._superconductor.execute(
                lambda l=layer, d=current: l.process(d)
            )
            all_results.append(lr)
            current = lr.output

        # Parallel phase
        if parallel_layers:
            p_coros = [
                self._superconductor.execute(lambda l=layer, d=current: l.process(d))
                for layer in parallel_layers
            ]
            p_results = list(await asyncio.gather(*p_coros))
            all_results.extend(p_results)
            current = self._fuse(p_results)

        return all_results, current

    # ------------------------------------------------------------------
    # Result fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _fuse(results: list[LayerResult]) -> Any:
        """Fuse parallel layer outputs by highest confidence."""
        if not results:
            return None
        best = max(results, key=lambda r: r.confidence)
        return best.output

    # ------------------------------------------------------------------
    # Parameter controls
    # ------------------------------------------------------------------

    def set_speed_mode(self, mode: SpeedMode) -> None:
        self._speed.set_mode(mode)
        self._config.speed_mode = mode

    def set_chain_mode(self, mode: ChainMode) -> None:
        self._config.chain_mode = mode
        logger.info("CHAiMERAChain mode set to %s", mode.value)

    def set_learning_rate(self, rate: float) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError("learning_rate must be 0.0–1.0")
        self._config.adaptive_learning_rate = rate

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def layer_count(self) -> int:
        return len(self._layers)

    @property
    def superconductor(self) -> Superconductor:
        return self._superconductor

    @property
    def speed_controller(self) -> SpeedController:
        return self._speed
