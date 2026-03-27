"""Geofencing for LoRa mesh nodes with AI-controlled alerts and defenses."""
from __future__ import annotations
import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.lora.geofence")


class GeofenceAction(Enum):
    ALERT = "alert"
    FREQUENCY_HOP = "frequency_hop"
    NETWORK_LOCK = "network_lock"


@dataclass
class GeofenceZone:
    zone_id: str
    center_lat: float
    center_lon: float
    radius_m: float
    actions: list[GeofenceAction] = field(default_factory=lambda: [GeofenceAction.ALERT])

    def contains(self, lat: float, lon: float) -> bool:
        """Check if (lat, lon) is within this geofence zone."""
        dist = _haversine_m(self.center_lat, self.center_lon, lat, lon)
        return dist <= self.radius_m


@dataclass
class GeofenceEvent:
    event_type: str   # "enter" or "exit"
    node_id: str
    zone_id: str
    lat: float
    lon: float
    timestamp: float = field(default_factory=time.time)
    actions_taken: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "node_id": self.node_id,
            "zone_id": self.zone_id,
            "lat": self.lat,
            "lon": self.lon,
            "timestamp": self.timestamp,
            "actions_taken": self.actions_taken,
        }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two WGS-84 coordinates."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class GeofenceManager:
    """Manages geofence zones and detects node boundary crossings."""

    def __init__(
        self, alert_callback: Optional[Callable[[GeofenceEvent], None]] = None
    ):
        self._zones: dict[str, GeofenceZone] = {}
        self._node_inside: dict[str, set[str]] = {}  # node_id -> set of zone_ids
        self._events: list[GeofenceEvent] = []
        self._alert_callback = alert_callback
        self._running = False

    def add_zone(self, zone: GeofenceZone) -> None:
        self._zones[zone.zone_id] = zone
        logger.info("Geofence zone added: %s (r=%.1fm)", zone.zone_id, zone.radius_m)

    def remove_zone(self, zone_id: str) -> None:
        self._zones.pop(zone_id, None)

    def update_node_position(
        self, node_id: str, lat: float, lon: float
    ) -> list[GeofenceEvent]:
        """Update node position and return any boundary-crossing events."""
        events: list[GeofenceEvent] = []
        inside_now = {
            zid for zid, z in self._zones.items() if z.contains(lat, lon)
        }
        was_inside = self._node_inside.get(node_id, set())

        for zid in inside_now - was_inside:
            zone = self._zones[zid]
            actions = [a.value for a in zone.actions]
            evt = GeofenceEvent(
                event_type="enter",
                node_id=node_id,
                zone_id=zid,
                lat=lat,
                lon=lon,
                actions_taken=actions,
            )
            events.append(evt)
            self._events.append(evt)
            logger.warning(
                "GEOFENCE ENTER: node=%s zone=%s actions=%s", node_id, zid, actions
            )
            if self._alert_callback:
                self._alert_callback(evt)

        for zid in was_inside - inside_now:
            zone = self._zones[zid]
            actions = [a.value for a in zone.actions]
            evt = GeofenceEvent(
                event_type="exit",
                node_id=node_id,
                zone_id=zid,
                lat=lat,
                lon=lon,
                actions_taken=actions,
            )
            events.append(evt)
            self._events.append(evt)
            logger.warning(
                "GEOFENCE EXIT: node=%s zone=%s actions=%s", node_id, zid, actions
            )
            if self._alert_callback:
                self._alert_callback(evt)

        self._node_inside[node_id] = inside_now
        return events

    def get_events(self) -> list[GeofenceEvent]:
        return list(self._events)

    def get_status(self) -> dict:
        return {
            "zone_count": len(self._zones),
            "tracked_nodes": len(self._node_inside),
            "total_events": len(self._events),
        }
