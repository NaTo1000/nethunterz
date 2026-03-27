"""Mesh visualization data layer for the GUI."""
from __future__ import annotations
import time
from typing import Any
from .firmware import LoRaFirmware
from .mesh_scanner import MeshScanner
from .geofence import GeofenceManager
from .attack_mirror import AttackMirrorDefense
from .autonomy import AutonomyEngine


class MeshGUI:
    """Provides structured data for mesh visualization in the GUI.

    Returns JSON-serializable dicts for node map, geofence boundaries,
    attack logs, and autonomy decisions.
    """

    def __init__(
        self,
        firmware: LoRaFirmware,
        scanner: MeshScanner,
        geofence: GeofenceManager,
        defense: AttackMirrorDefense,
        autonomy: AutonomyEngine,
    ):
        self.firmware = firmware
        self.scanner = scanner
        self.geofence = geofence
        self.defense = defense
        self.autonomy = autonomy

    def get_node_map(self) -> dict[str, Any]:
        nodes = [r.to_dict() for r in self.scanner.get_all_nodes()]
        return {
            "timestamp": time.time(),
            "nodes": nodes,
            "firmware_status": self.firmware.get_status(),
        }

    def get_geofence_view(self) -> dict[str, Any]:
        zones = [
            {
                "zone_id": z.zone_id,
                "center_lat": z.center_lat,
                "center_lon": z.center_lon,
                "radius_m": z.radius_m,
                "actions": [a.value for a in z.actions],
            }
            for z in self.geofence._zones.values()
        ]
        events = [e.to_dict() for e in self.geofence.get_events()]
        return {
            "timestamp": time.time(),
            "zones": zones,
            "events": events,
        }

    def get_attack_log(self) -> dict[str, Any]:
        return {
            "timestamp": time.time(),
            "defense_events": [e.to_dict() for e in self.defense.get_defense_events()],
            "isolated_nodes": self.defense.get_isolated_nodes(),
        }

    def get_autonomy_log(self) -> dict[str, Any]:
        return {
            "timestamp": time.time(),
            "decisions": [d.to_dict() for d in self.autonomy.get_decisions()],
        }

    def get_full_dashboard(self) -> dict[str, Any]:
        return {
            "node_map": self.get_node_map(),
            "geofence": self.get_geofence_view(),
            "attack_log": self.get_attack_log(),
            "autonomy_log": self.get_autonomy_log(),
        }
