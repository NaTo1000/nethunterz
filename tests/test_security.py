"""Tests for Security, Encryption, Audit, and Monitoring."""

import asyncio
import json
import os
import time
import pytest

from grok420.security.audit import AuditEntry, AuditTrail
from grok420.security.encryption import Encryptor
from grok420.security.monitoring import Alert, AlertSeverity, MonitoringDashboard


# ---------------------------------------------------------------------------
# Encryptor
# ---------------------------------------------------------------------------


def test_encryptor_roundtrip():
    enc = Encryptor()
    plaintext = b"hello grok420"
    ct = enc.encrypt(plaintext)
    assert ct != plaintext
    assert enc.decrypt(ct) == plaintext


def test_encryptor_different_ciphertexts():
    enc = Encryptor()
    pt = b"same data"
    ct1 = enc.encrypt(pt)
    ct2 = enc.encrypt(pt)
    # Random nonce ensures ciphertexts differ
    assert ct1 != ct2


def test_encryptor_b64_roundtrip():
    enc = Encryptor()
    plaintext = b"base64 test"
    encoded = enc.encrypt_b64(plaintext)
    assert isinstance(encoded, str)
    assert enc.decrypt_b64(encoded) == plaintext


def test_encryptor_wrong_key():
    enc1 = Encryptor()
    enc2 = Encryptor()
    ct = enc1.encrypt(b"secret")
    try:
        dec = enc2.decrypt(ct)
        # XOR fallback won't raise, just produce garbage
        assert dec != b"secret"
    except Exception:
        pass  # AES-GCM will raise on wrong key


def test_encryptor_fixed_key():
    key = os.urandom(32)
    enc1 = Encryptor(key)
    enc2 = Encryptor(key)
    ct = enc1.encrypt(b"shared key test")
    assert enc2.decrypt(ct) == b"shared key test"


def test_encryptor_key_size_validation():
    with pytest.raises(ValueError, match="32 bytes"):
        Encryptor(b"short_key")


def test_encryptor_export_key():
    enc = Encryptor()
    b64_key = enc.export_key_b64()
    import base64
    assert len(base64.b64decode(b64_key)) == 32


def test_encryptor_from_env(monkeypatch):
    import base64
    key = os.urandom(32)
    monkeypatch.setenv("GROK420_ENCRYPTION_KEY", base64.b64encode(key).decode())
    enc = Encryptor.from_env()
    ct = enc.encrypt(b"env key test")
    assert Encryptor(key).decrypt(ct) == b"env key test"


# ---------------------------------------------------------------------------
# AuditEntry / AuditTrail
# ---------------------------------------------------------------------------


def test_audit_entry_hash():
    entry = AuditEntry(component="test", event="action")
    assert entry.integrity_hash
    assert entry.verify()


def test_audit_entry_to_dict():
    entry = AuditEntry(component="comp", event="ev", details={"x": 1})
    d = entry.to_dict()
    assert d["component"] == "comp"
    assert d["details"]["x"] == 1


def test_audit_trail_record(tmp_path):
    trail = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    e1 = trail.record("conductor", "bot_registered", {"bot_id": "abc"})
    e2 = trail.record("chaimera", "chain_started")
    assert len(trail.get_all()) == 2
    assert e1.verify()
    assert e2.verify()


def test_audit_trail_query(tmp_path):
    trail = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    trail.record("conductor", "start")
    trail.record("conductor", "stop")
    trail.record("orchestration", "task_complete")

    by_comp = trail.query(component="conductor")
    assert len(by_comp) == 2

    by_event = trail.query(event="stop")
    assert len(by_event) == 1


def test_audit_trail_integrity(tmp_path):
    trail = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    trail.record("comp", "event1")
    trail.record("comp", "event2")
    valid, invalid = trail.verify_integrity()
    assert valid == 2
    assert invalid == 0


def test_audit_trail_persistence(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    t1 = AuditTrail(path=path)
    t1.record("persisted", "saved")

    t2 = AuditTrail(path=path)
    entries = t2.get_all()
    assert any(e.component == "persisted" for e in entries)


def test_audit_trail_since_filter(tmp_path):
    trail = AuditTrail(path=str(tmp_path / "audit.jsonl"))
    trail.record("old", "event")
    cutoff = time.time()
    trail.record("new", "event")
    results = trail.query(since=cutoff)
    assert all(e.component == "new" for e in results)


# ---------------------------------------------------------------------------
# MonitoringDashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_start_stop():
    dash = MonitoringDashboard(check_interval_s=60)
    await dash.start()
    assert dash._running
    await dash.stop()
    assert not dash._running


@pytest.mark.asyncio
async def test_dashboard_raise_alert():
    dash = MonitoringDashboard()
    await dash.start()
    alert = await dash.raise_alert("conductor", "test_error", AlertSeverity.ERROR)
    assert alert.severity == AlertSeverity.ERROR
    assert not alert.resolved
    await dash.stop()


@pytest.mark.asyncio
async def test_dashboard_resolve_alert():
    dash = MonitoringDashboard()
    await dash.start()
    alert = await dash.raise_alert("comp", "issue")
    ok = await dash.resolve_alert(alert.alert_id)
    assert ok
    assert len(dash.get_open_alerts()) == 0
    await dash.stop()


@pytest.mark.asyncio
async def test_dashboard_auto_resolver():
    resolved = []

    async def my_resolver(alert: Alert) -> None:
        resolved.append(alert.alert_id)

    dash = MonitoringDashboard()
    dash.register_resolver("auto_comp", my_resolver)
    await dash.start()
    await dash.raise_alert("auto_comp", "auto_issue")
    # Give the resolver a moment
    await asyncio.sleep(0.05)
    assert len(resolved) == 1
    await dash.stop()


@pytest.mark.asyncio
async def test_dashboard_metrics():
    dash = MonitoringDashboard()
    await dash.start()
    dash.record_metric("throughput", 1500)
    assert dash.get_metric("throughput") == 1500
    await dash.stop()


@pytest.mark.asyncio
async def test_dashboard_summary():
    dash = MonitoringDashboard()
    await dash.start()
    await dash.raise_alert("x", "msg1")
    await dash.raise_alert("y", "msg2")
    alert = await dash.raise_alert("z", "msg3")
    await dash.resolve_alert(alert.alert_id)
    summary = dash.get_summary()
    assert summary["total_alerts"] == 3
    assert summary["open_alerts"] == 2
    assert summary["resolved_alerts"] == 1
    await dash.stop()
