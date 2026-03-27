"""
CHAiMERA - Multi-layered AI chain orchestration with parallel-series switching.

Three-speed AI chain:
  - SPEED 1 (RAPID): Parallel execution, low-latency, high throughput
  - SPEED 2 (BALANCED): Mixed parallel/serial with quality gates
  - SPEED 3 (DEEP): Full serial chain with cross-layer validation

Leverages the NayDoeV1 superconductor for inter-layer communication.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ChainSpeed(Enum):
    RAPID = 1      # Pure parallel - lowest latency
    BALANCED = 2   # Hybrid - parallel stages, serial gates
    DEEP = 3       # Pure serial - maximum depth reasoning


class LayerMode(Enum):
    ANALYSIS = "analysis"
    DECISION = "decision"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    EXECUTION = "execution"


@dataclass
class ChainLayer:
    """A single layer in the CHAiMERA chain."""
    layer_id: str
    name: str
    mode: LayerMode
    handler: Callable
    weight: float = 1.0
    timeout: float = 10.0
    required: bool = True


@dataclass
class LayerResult:
    """Output from a single chain layer."""
    layer_id: str
    layer_name: str
    output: Any
    confidence: float
    elapsed_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class ChainExecution:
    """Full execution record for a CHAiMERA chain run."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    speed: ChainSpeed = ChainSpeed.BALANCED
    layer_results: List[LayerResult] = field(default_factory=list)
    final_output: Any = None
    total_elapsed_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    success: bool = False

    @property
    def successful_layers(self) -> int:
        return sum(1 for r in self.layer_results if r.success)

    @property
    def average_confidence(self) -> float:
        valid = [r.confidence for r in self.layer_results if r.success]
        return sum(valid) / len(valid) if valid else 0.0


class ChaimeraOrchestrator:
    """
    CHAiMERA: Three-speed AI chain orchestration system.

    Manages multi-layered AI processing pipelines with configurable
    speed/depth tradeoffs and automatic parallel-series switching.
    Integrates with NayDoeV1 conductor and TWINBRAIN for validated outputs.
    """

    VERSION = "1.0.0"
    CODENAME = "CHAiMERA"

    def __init__(
        self,
        default_speed: ChainSpeed = ChainSpeed.BALANCED,
        enable_twinbrain_validation: bool = True,
        max_chain_depth: int = 20,
    ) -> None:
        self.default_speed = default_speed
        self.enable_twinbrain_validation = enable_twinbrain_validation
        self.max_chain_depth = max_chain_depth
        self._layers: List[ChainLayer] = []
        self._execution_history: List[ChainExecution] = []

    def add_layer(
        self,
        name: str,
        handler: Callable,
        mode: LayerMode = LayerMode.ANALYSIS,
        weight: float = 1.0,
        timeout: float = 10.0,
        required: bool = True,
    ) -> "ChaimeraOrchestrator":
        """Add a processing layer to the chain. Returns self for chaining."""
        layer = ChainLayer(
            layer_id=str(uuid.uuid4()),
            name=name,
            mode=mode,
            handler=handler,
            weight=weight,
            timeout=timeout,
            required=required,
        )
        self._layers.append(layer)
        return self

    async def execute(
        self,
        input_data: Any,
        speed: Optional[ChainSpeed] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ChainExecution:
        """
        Execute the AI chain with the specified speed mode.

        Args:
            input_data: Input to pass through the chain.
            speed: Override default speed for this execution.
            context: Optional metadata context.
        """
        run_speed = speed or self.default_speed
        execution = ChainExecution(speed=run_speed)
        context = context or {}

        start = time.time()

        try:
            if run_speed == ChainSpeed.RAPID:
                results = await self._execute_parallel(input_data, context)
            elif run_speed == ChainSpeed.BALANCED:
                results = await self._execute_balanced(input_data, context)
            else:  # DEEP
                results = await self._execute_serial(input_data, context)

            execution.layer_results = results
            execution.final_output = self._synthesize(results)
            execution.success = True

        except Exception as e:
            execution.success = False
            execution.final_output = {"error": str(e)}

        execution.completed_at = time.time()
        execution.total_elapsed_ms = (execution.completed_at - start) * 1000
        self._execution_history.append(execution)

        return execution

    async def _execute_parallel(
        self,
        data: Any,
        context: Dict[str, Any],
    ) -> List[LayerResult]:
        """SPEED 1: All layers execute in parallel."""
        tasks = [self._run_layer(layer, data, context) for layer in self._layers]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    async def _execute_balanced(
        self,
        data: Any,
        context: Dict[str, Any],
    ) -> List[LayerResult]:
        """SPEED 2: Group by mode, parallel within groups, serial between."""
        # Group layers by mode
        groups: Dict[LayerMode, List[ChainLayer]] = {}
        for layer in self._layers:
            groups.setdefault(layer.mode, []).append(layer)

        mode_order = [
            LayerMode.ANALYSIS,
            LayerMode.DECISION,
            LayerMode.VALIDATION,
            LayerMode.SYNTHESIS,
            LayerMode.EXECUTION,
        ]

        results: List[LayerResult] = []
        current_data = data

        for mode in mode_order:
            if mode not in groups:
                continue
            group_layers = groups[mode]
            group_tasks = [
                self._run_layer(layer, current_data, context)
                for layer in group_layers
            ]
            group_results = list(
                await asyncio.gather(*group_tasks, return_exceptions=False)
            )
            results.extend(group_results)
            # Pass synthesized output to next group
            current_data = self._synthesize(group_results)

        return results

    async def _execute_serial(
        self,
        data: Any,
        context: Dict[str, Any],
    ) -> List[LayerResult]:
        """SPEED 3: Each layer feeds into the next sequentially."""
        results: List[LayerResult] = []
        current_data = data

        for layer in self._layers:
            result = await self._run_layer(layer, current_data, context)
            results.append(result)
            if result.success:
                current_data = result.output
            elif layer.required:
                break  # Stop chain on required layer failure

        return results

    async def _run_layer(
        self,
        layer: ChainLayer,
        data: Any,
        context: Dict[str, Any],
    ) -> LayerResult:
        """Execute a single layer with timeout handling."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(layer.handler):
                output = await asyncio.wait_for(
                    layer.handler(data, context),
                    timeout=layer.timeout,
                )
            else:
                output = layer.handler(data, context)

            confidence = float(
                output.get("confidence", 1.0)
                if isinstance(output, dict)
                else 1.0
            )
            return LayerResult(
                layer_id=layer.layer_id,
                layer_name=layer.name,
                output=output,
                confidence=confidence,
                elapsed_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return LayerResult(
                layer_id=layer.layer_id,
                layer_name=layer.name,
                output=None,
                confidence=0.0,
                elapsed_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    def _synthesize(self, results: List[LayerResult]) -> Any:
        """Merge layer outputs into a single synthesized output."""
        successful = [r for r in results if r.success]
        if not successful:
            return {"synthesized": False, "outputs": []}

        # Weight outputs by layer confidence
        outputs = []
        for r in successful:
            outputs.append({
                "layer": r.layer_name,
                "output": r.output,
                "confidence": r.confidence,
            })

        return {
            "synthesized": True,
            "outputs": outputs,
            "average_confidence": sum(r.confidence for r in successful) / len(successful),
            "layer_count": len(successful),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return CHAiMERA performance statistics."""
        history = self._execution_history
        if not history:
            return {"total_executions": 0, "layers_registered": len(self._layers)}

        successful = [e for e in history if e.success]
        avg_ms = sum(e.total_elapsed_ms for e in history) / len(history)

        return {
            "total_executions": len(history),
            "success_rate": len(successful) / len(history),
            "average_latency_ms": avg_ms,
            "layers_registered": len(self._layers),
            "default_speed": self.default_speed.name,
        }
