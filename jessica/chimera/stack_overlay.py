"""3×3×3 Stack Overlay — the spatial execution model for CHAiMERA.

The overlay is a three‑dimensional grid of *cells*, each of which represents
an execution slot that can host a running tool or analysis task.

Dimensions
----------
* **Depth** (layers) — e.g. reconnaissance → exploitation → post‑exploitation
* **Width** (lanes)  — parallel processing lanes within each layer
* **Height** (stages) — pipeline stages within a lane: input → process → output
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jessica.chimera.stack_overlay")


class CellState(str, Enum):
    IDLE = "idle"
    RESERVED = "reserved"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StackCell:
    """A single cell in the 3D overlay grid."""

    layer: int  # depth index
    lane: int   # width index
    stage: int  # height index
    state: CellState = CellState.IDLE
    assigned_tool: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def coords(self) -> tuple[int, int, int]:
        return (self.layer, self.lane, self.stage)

    def __repr__(self) -> str:
        return f"Cell({self.layer},{self.lane},{self.stage} state={self.state.value})"


class StackOverlay:
    """The 3×3×3 (configurable) execution grid.

    Provides cell allocation, layer/lane queries, and state tracking so that
    the CHAiMERA chain engine can map workflow steps onto the grid.
    """

    def __init__(self, depth: int = 3, width: int = 3, height: int = 3) -> None:
        self.depth = depth
        self.width = width
        self.height = height
        self._grid: list[list[list[StackCell]]] = [
            [
                [StackCell(layer=d, lane=w, stage=h) for h in range(height)]
                for w in range(width)
            ]
            for d in range(depth)
        ]
        logger.info("StackOverlay initialised: %dx%dx%d (%d cells)", depth, width, height, self.total_cells)

    # ── properties ────────────────────────────────────────

    @property
    def total_cells(self) -> int:
        return self.depth * self.width * self.height

    # ── cell access ───────────────────────────────────────

    def get_cell(self, layer: int, lane: int, stage: int) -> StackCell:
        return self._grid[layer][lane][stage]

    def get_layer(self, layer: int) -> list[list[StackCell]]:
        """Return all cells in a given depth layer."""
        return self._grid[layer]

    def get_lane(self, layer: int, lane: int) -> list[StackCell]:
        """Return all stage cells for a specific lane within a layer."""
        return self._grid[layer][lane]

    def all_cells(self) -> list[StackCell]:
        """Flat list of every cell in the overlay."""
        return [
            cell
            for layer in self._grid
            for lane in layer
            for cell in lane
        ]

    # ── allocation ────────────────────────────────────────

    def reserve_cell(self, layer: int, lane: int, stage: int, tool: str) -> StackCell:
        cell = self.get_cell(layer, lane, stage)
        if cell.state not in (CellState.IDLE, CellState.COMPLETED, CellState.ERROR):
            raise RuntimeError(f"Cell {cell.coords} is not available (state={cell.state.value})")
        cell.state = CellState.RESERVED
        cell.assigned_tool = tool
        logger.debug("Reserved cell %s for %s", cell.coords, tool)
        return cell

    def activate_cell(self, layer: int, lane: int, stage: int) -> None:
        cell = self.get_cell(layer, lane, stage)
        cell.state = CellState.ACTIVE

    def complete_cell(self, layer: int, lane: int, stage: int, metadata: dict[str, Any] | None = None) -> None:
        cell = self.get_cell(layer, lane, stage)
        cell.state = CellState.COMPLETED
        if metadata:
            cell.metadata.update(metadata)

    def error_cell(self, layer: int, lane: int, stage: int, error: str) -> None:
        cell = self.get_cell(layer, lane, stage)
        cell.state = CellState.ERROR
        cell.metadata["error"] = error

    def release_cell(self, layer: int, lane: int, stage: int) -> None:
        cell = self.get_cell(layer, lane, stage)
        cell.state = CellState.IDLE
        cell.assigned_tool = None
        cell.metadata.clear()

    # ── queries ───────────────────────────────────────────

    def idle_cells(self) -> list[StackCell]:
        return [c for c in self.all_cells() if c.state == CellState.IDLE]

    def active_cells(self) -> list[StackCell]:
        return [c for c in self.all_cells() if c.state == CellState.ACTIVE]

    def find_idle_in_layer(self, layer: int) -> list[StackCell]:
        return [
            cell
            for lane in self._grid[layer]
            for cell in lane
            if cell.state == CellState.IDLE
        ]

    def utilisation(self) -> float:
        """Return the fraction of cells that are reserved or active."""
        busy = sum(1 for c in self.all_cells() if c.state in (CellState.RESERVED, CellState.ACTIVE))
        return busy / self.total_cells if self.total_cells else 0.0
