"""Tests for lora_mesh.attack_mirror module."""
from __future__ import annotations

from lora_mesh.attack_mirror import (
    AttackMirrorDefense,
    ThreatLevel,
)


def test_attack_mirror_init():
    defense = AttackMirrorDefense()
    status = defense.get_status()
    assert status["running"] is False
    assert status["anomalies_detected"] == 0
    assert status["defense_events"] == 0
    assert status["isolated_nodes"] == []


def test_analyze_packet_normal_traffic_returns_none():
    defense = AttackMirrorDefense()
    result = defense.analyze_packet(
        source_node="node_1",
        payload_bytes=b"\x01\x02\x03\x04",
        rssi=-70.0,
        frequency_mhz=915.0,
    )
    assert result is None


def test_analyze_packet_replay_attack_detected():
    defense = AttackMirrorDefense()
    payload = b"\xca\xfe\xba\xbe"

    # Fill the payload window with the same payload
    for _ in range(defense.DUPLICATE_PAYLOAD_WINDOW):
        defense._payload_window.append(payload.hex())

    # Now send it again - should be flagged as replay
    result = defense.analyze_packet(
        source_node="node_replay",
        payload_bytes=payload,
        rssi=-70.0,
        frequency_mhz=915.0,
    )
    # replay adds score=2 -> MEDIUM -> LOG action (returns DefenseEvent)
    assert result is not None
    assert result.anomaly.threat_level in (
        ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL
    )


def test_analyze_packet_high_rssi_anomaly():
    defense = AttackMirrorDefense()
    # RSSI above threshold (-30 dBm) should add score
    result = defense.analyze_packet(
        source_node="node_strong",
        payload_bytes=b"\xaa\xbb\xcc\xdd",
        rssi=-20.0,  # above -30.0 threshold
        frequency_mhz=915.0,
    )
    assert result is not None
    assert result.anomaly.rssi == -20.0


def test_isolated_node_packets_dropped():
    defense = AttackMirrorDefense()
    defense._isolated_nodes.add("node_bad")
    result = defense.analyze_packet(
        source_node="node_bad",
        payload_bytes=b"\x00\x01\x02\x03",
        rssi=-60.0,
        frequency_mhz=915.0,
    )
    assert result is None


def test_release_node_removes_from_isolated():
    defense = AttackMirrorDefense()
    defense._isolated_nodes.add("node_bad")
    defense.release_node("node_bad")
    assert "node_bad" not in defense.get_isolated_nodes()


def test_get_status_fields():
    defense = AttackMirrorDefense()
    status = defense.get_status()
    assert "running" in status
    assert "anomalies_detected" in status
    assert "defense_events" in status
    assert "isolated_nodes" in status
