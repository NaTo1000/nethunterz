"""Tests for lora_mesh.geofence module."""
from __future__ import annotations

import pytest

from lora_mesh.geofence import (
    GeofenceManager,
    GeofenceZone,
    _haversine_m,
)


# ---------------------------------------------------------------------------
# _haversine_m tests
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    dist = _haversine_m(37.0, -122.0, 37.0, -122.0)
    assert dist == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # ~111 km per degree latitude
    dist = _haversine_m(0.0, 0.0, 1.0, 0.0)
    assert 110_000 < dist < 112_000


# ---------------------------------------------------------------------------
# GeofenceZone tests
# ---------------------------------------------------------------------------

def test_geofence_zone_contains_inside():
    zone = GeofenceZone(
        zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=500.0
    )
    # Same point is inside
    assert zone.contains(37.0, -122.0) is True


def test_geofence_zone_contains_outside():
    zone = GeofenceZone(
        zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=100.0
    )
    # 1 degree latitude away is ~111 km - definitely outside 100 m radius
    assert zone.contains(38.0, -122.0) is False


def test_geofence_zone_boundary():
    # Place node exactly at the radius boundary
    zone = GeofenceZone(
        zone_id="z1", center_lat=0.0, center_lon=0.0, radius_m=111_320.0
    )
    # ~1 degree lat = 111,320 m
    assert zone.contains(1.0, 0.0) is True  # right at boundary (approx)


# ---------------------------------------------------------------------------
# GeofenceManager tests
# ---------------------------------------------------------------------------

def test_geofence_manager_add_zone():
    mgr = GeofenceManager()
    zone = GeofenceZone(zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=1000.0)
    mgr.add_zone(zone)
    assert mgr.get_status()["zone_count"] == 1


def test_geofence_manager_enter_event():
    alerts = []
    mgr = GeofenceManager(alert_callback=alerts.append)
    zone = GeofenceZone(zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=1000.0)
    mgr.add_zone(zone)

    events = mgr.update_node_position("node_1", 37.0, -122.0)
    assert len(events) == 1
    assert events[0].event_type == "enter"
    assert events[0].node_id == "node_1"
    assert len(alerts) == 1


def test_geofence_manager_exit_event():
    mgr = GeofenceManager()
    zone = GeofenceZone(zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=1000.0)
    mgr.add_zone(zone)

    # Enter first
    mgr.update_node_position("node_1", 37.0, -122.0)
    # Then exit
    events = mgr.update_node_position("node_1", 50.0, 10.0)
    exit_events = [e for e in events if e.event_type == "exit"]
    assert len(exit_events) == 1


def test_geofence_no_event_when_stays_inside():
    mgr = GeofenceManager()
    zone = GeofenceZone(zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=1000.0)
    mgr.add_zone(zone)

    mgr.update_node_position("node_1", 37.0, -122.0)  # enter
    events = mgr.update_node_position("node_1", 37.0, -122.0)  # still inside
    assert len(events) == 0


def test_geofence_no_event_when_stays_outside():
    mgr = GeofenceManager()
    zone = GeofenceZone(zone_id="z1", center_lat=37.0, center_lon=-122.0, radius_m=100.0)
    mgr.add_zone(zone)

    events1 = mgr.update_node_position("node_1", 50.0, 10.0)
    events2 = mgr.update_node_position("node_1", 51.0, 11.0)
    assert len(events1) == 0
    assert len(events2) == 0


def test_geofence_get_status():
    mgr = GeofenceManager()
    status = mgr.get_status()
    assert "zone_count" in status
    assert "tracked_nodes" in status
    assert "total_events" in status
