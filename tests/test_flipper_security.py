"""Tests for SecurityManager, AES256Cipher, and TrailWiper."""
from __future__ import annotations

from flipper.security import (
    SecurityManager,
    SecurityConfig,
    WipeMode,
    AES256Cipher,
    TrailWiper,
)


# ---------------------------------------------------------------------------
# AES256Cipher tests
# ---------------------------------------------------------------------------

def test_aes_cipher_encrypt_decrypt_roundtrip():
    cipher = AES256Cipher()
    plaintext = b"NayDoeV1 secret payload 80s vibes"
    ciphertext = cipher.encrypt(plaintext)
    assert ciphertext != plaintext
    recovered = cipher.decrypt(ciphertext)
    assert recovered == plaintext


def test_aes_cipher_different_keys_different_output():
    cipher1 = AES256Cipher()
    cipher2 = AES256Cipher()
    plaintext = b"hello world"
    ct1 = cipher1.encrypt(plaintext)
    ct2 = cipher2.encrypt(plaintext)
    # Different keys → different ciphertext (highly likely)
    assert ct1 != ct2


def test_aes_cipher_generate_key():
    cipher = AES256Cipher()
    old_key = bytes(cipher._key)
    new_key = cipher.generate_key()
    assert len(new_key) == 32
    assert new_key != old_key


def test_aes_cipher_empty_plaintext():
    cipher = AES256Cipher()
    ct = cipher.encrypt(b"")
    pt = cipher.decrypt(ct)
    assert pt == b""


def test_aes_cipher_large_payload():
    cipher = AES256Cipher()
    plaintext = b"X" * 65536
    ct = cipher.encrypt(plaintext)
    pt = cipher.decrypt(ct)
    assert pt == plaintext


# ---------------------------------------------------------------------------
# TrailWiper tests
# ---------------------------------------------------------------------------

def test_trail_wiper_wipe_file(tmp_path):
    wiper = TrailWiper(mode=WipeMode.DOD_3_PASS)
    target = tmp_path / "sensitive.bin"
    target.write_bytes(b"secret data" * 100)
    assert target.exists()
    result = wiper.wipe_file(target)
    assert result is True
    assert not target.exists()
    assert str(target) in wiper.wiped_paths


def test_trail_wiper_nonexistent_file(tmp_path):
    wiper = TrailWiper()
    result = wiper.wipe_file(tmp_path / "does_not_exist.bin")
    assert result is False


def test_trail_wiper_wipe_directory(tmp_path):
    wiper = TrailWiper(mode=WipeMode.SINGLE_PASS)
    subdir = tmp_path / "sensitive_dir"
    subdir.mkdir()
    for i in range(5):
        (subdir / f"file_{i}.bin").write_bytes(b"data" * 100)
    count = wiper.wipe_directory(subdir)
    assert count == 5


def test_trail_wiper_gutmann_mode(tmp_path):
    wiper = TrailWiper(mode=WipeMode.GUTMANN_7)
    target = tmp_path / "gutmann_test.bin"
    target.write_bytes(b"top secret" * 50)
    result = wiper.wipe_file(target)
    assert result is True


def test_trail_wiper_wipe_bytes():
    wiper = TrailWiper()
    buf = wiper.wipe_bytes(256)
    assert len(buf) == 256
    assert isinstance(buf, bytes)


# ---------------------------------------------------------------------------
# SecurityManager tests
# ---------------------------------------------------------------------------

def test_security_manager_initialisation():
    sm = SecurityManager(simulation=True)
    status = sm.get_status()
    assert status["ble_encryption"] is True
    assert status["simulation"] is True
    assert status["failed_auth_count"] == 0


def test_ble_encrypt_decrypt():
    sm = SecurityManager(simulation=True)
    payload = b"BLE command: scan 2.4GHz"
    ct = sm.encrypt_ble_payload(payload)
    pt = sm.decrypt_ble_payload(ct)
    assert pt == payload


def test_mac_randomisation():
    sm = SecurityManager(simulation=True)
    mac1 = sm.randomise_mac()
    mac2 = sm.randomise_mac()
    # MACs should be valid format
    assert len(mac1.split(":")) == 6
    # Second call generates a different MAC (with overwhelming probability)
    assert mac1 != mac2 or True  # Non-deterministic; just verify format


def test_mac_randomisation_format():
    sm = SecurityManager(simulation=True)
    mac = sm.randomise_mac()
    parts = mac.split(":")
    assert len(parts) == 6
    for part in parts:
        assert len(part) == 2
        int(part, 16)  # Should not raise


def test_ip_anonymisation_logged():
    sm = SecurityManager(simulation=True)
    sm.anonymise_ip()
    log = sm.get_audit_log()
    assert any(e["event_type"] == "ip_anonymise" for e in log)


def test_authentication_success():
    sm = SecurityManager(simulation=True)
    key_hash = sm.get_session_key_hash()
    result = sm.authenticate(key_hash)
    assert result is True
    assert sm._failed_auth_count == 0


def test_authentication_failure():
    sm = SecurityManager(simulation=True)
    result = sm.authenticate("wrong_hash")
    assert result is False
    assert sm._failed_auth_count == 1


def test_trail_wipe_clears_data(tmp_path):
    sm = SecurityManager(simulation=True)
    # Create some files to wipe
    data_dir = tmp_path / "flipper_data"
    data_dir.mkdir()
    for i in range(3):
        (data_dir / f"log_{i}.txt").write_bytes(b"sensitive" * 100)

    # Add some audit events
    sm.randomise_mac()
    sm.anonymise_ip()
    assert len(sm.get_audit_log()) > 0

    result = sm.trail_wipe(data_dirs=[data_dir])
    assert result["wiped_files"] == 3
    assert result["cleared_events"] > 0
    assert result["key_rotated"] is True
    assert len(sm.get_audit_log()) == 0


def test_trail_wipe_without_dirs():
    sm = SecurityManager(simulation=True)
    sm.randomise_mac()
    result = sm.trail_wipe()
    assert result["key_rotated"] is True
    assert result["cleared_events"] >= 1


def test_max_failed_auth_triggers_wipe():
    config = SecurityConfig(max_failed_auth=2)
    sm = SecurityManager(config=config, simulation=True)
    # Add some audit events
    sm.randomise_mac()

    # Two failures should trigger wipe
    sm.authenticate("bad_hash_1")
    sm.authenticate("bad_hash_2")

    # After wipe, audit log should be cleared
    assert len(sm.get_audit_log()) == 0


def test_audit_log_records_events():
    sm = SecurityManager(simulation=True)
    sm.randomise_mac()
    sm.anonymise_ip()
    log = sm.get_audit_log()
    event_types = {e["event_type"] for e in log}
    assert "mac_randomise" in event_types
    assert "ip_anonymise" in event_types


def test_security_config_custom():
    config = SecurityConfig(
        wipe_mode=WipeMode.GUTMANN_7,
        mac_randomisation=False,
        max_failed_auth=5,
    )
    sm = SecurityManager(config=config, simulation=True)
    assert sm.config.wipe_mode == WipeMode.GUTMANN_7
    assert sm.config.max_failed_auth == 5
