"""Cluster Manager — auto-discovery, health checks, and load balancing."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from grok420.config import OrchestrationConfig

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class ClusterNode:
    """Represents a single transformer-cluster node."""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    address: str = "localhost"
    port: int = 0
    status: NodeStatus = NodeStatus.ONLINE
    last_check: float = field(default_factory=time.monotonic)
    task_count: int = 0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == NodeStatus.ONLINE

    @property
    def load(self) -> float:
        """Relative load score; higher = more loaded."""
        return float(self.task_count)


class ClusterManager:
    """Manages a pool of :class:`ClusterNode` instances.

    Features
    --------
    * Auto-discovery: synthetic nodes added on demand during start.
    * Health checks: periodic liveness probes with state transitions.
    * Load balancing: round-robin and least-loaded strategies.
    """

    def __init__(self, config: OrchestrationConfig) -> None:
        self._config = config
        self._nodes: dict[str, ClusterNode] = {}
        self._rr_index = 0
        self._lock = asyncio.Lock()
        self._health_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._config.auto_discovery:
            await self._discover_nodes()
        self._health_task = asyncio.create_task(self._health_loop())
        logger.info("ClusterManager started with %d nodes", len(self._nodes))

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        logger.info("ClusterManager stopped")

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    async def add_node(self, node: ClusterNode) -> None:
        async with self._lock:
            self._nodes[node.node_id] = node
        logger.debug("Node added: %s @ %s:%d", node.node_id, node.address, node.port)

    async def remove_node(self, node_id: str) -> None:
        async with self._lock:
            self._nodes.pop(node_id, None)
        logger.debug("Node removed: %s", node_id)

    async def get_healthy_nodes(self) -> list[ClusterNode]:
        async with self._lock:
            return [n for n in self._nodes.values() if n.is_healthy]

    # ------------------------------------------------------------------
    # Load balancing
    # ------------------------------------------------------------------

    async def pick_node(
        self, strategy: str | None = None
    ) -> ClusterNode | None:
        """Return a node according to the configured strategy."""
        strat = strategy or self._config.load_balance_strategy
        healthy = await self.get_healthy_nodes()
        if not healthy:
            return None
        if strat == "least_loaded":
            return min(healthy, key=lambda n: n.load)
        # Default: round-robin
        async with self._lock:
            node = healthy[self._rr_index % len(healthy)]
            self._rr_index = (self._rr_index + 1) % len(healthy)
        return node

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _discover_nodes(self) -> None:
        """Synthesise cluster_count virtual nodes (no real network calls)."""
        for i in range(self._config.cluster_count):
            node = ClusterNode(
                address="cluster-node",
                port=50000 + i,
                metadata={"index": i, "synthetic": True},
            )
            await self.add_node(node)
        logger.info("Auto-discovered %d nodes", self._config.cluster_count)

    async def _health_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._config.health_check_interval_s)
            await self._run_health_checks()

    async def _run_health_checks(self) -> None:
        async with self._lock:
            nodes = list(self._nodes.values())
        for node in nodes:
            # Simulate health check — real deployments perform a TCP ping
            node.last_check = time.monotonic()
            if node.error_count > 5:
                node.status = NodeStatus.DEGRADED
            elif node.error_count > 10:
                node.status = NodeStatus.OFFLINE
            else:
                node.status = NodeStatus.ONLINE
        logger.debug("Health check complete: %d nodes", len(nodes))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def get_cluster_status(self) -> list[dict[str, Any]]:
        return [
            {
                "node_id": n.node_id,
                "address": f"{n.address}:{n.port}",
                "status": n.status.value,
                "task_count": n.task_count,
                "error_count": n.error_count,
            }
            for n in self._nodes.values()
        ]
