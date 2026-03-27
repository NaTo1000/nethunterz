"""
Tests for BLCKjACK Arch Security Layer.
"""
import pytest
from blckjack_arch.security import (
    AnonymizationLevel,
    BLCKjACKArch,
    IPAnonymizer,
    MACRandomizer,
    TrailWipeEngine,
    WipeStandard,
)


@pytest.fixture
def mac_randomizer():
    return MACRandomizer()


@pytest.fixture
def ip_anonymizer():
    return IPAnonymizer()


@pytest.fixture
def trail_wipe():
    return TrailWipeEngine()


@pytest.fixture
def blckjack():
    return BLCKjACKArch(anonymization_level=AnonymizationLevel.HIGH)


# ── MAC Randomizer Tests ───────────────────────────────────────────────────────

def test_mac_generate_format(mac_randomizer):
    mac = mac_randomizer.generate()
    parts = mac.split(":")
    assert len(parts) == 6
    assert all(len(p) == 2 for p in parts)


def test_mac_locally_administered(mac_randomizer):
    mac = mac_randomizer.generate(locally_administered=True)
    first = int(mac.split(":")[0], 16)
    assert first & 0x02  # LA bit set
    assert not (first & 0x01)  # MC bit clear


def test_mac_unique_each_time(mac_randomizer):
    macs = {mac_randomizer.generate() for _ in range(100)}
    # Should generate mostly unique MACs
    assert len(macs) > 90


@pytest.mark.asyncio
async def test_mac_randomize_interface(mac_randomizer):
    new_mac = await mac_randomizer.randomize("wlan0")
    assert ":" in new_mac
    assert mac_randomizer.current_mac == new_mac


def test_mac_history(mac_randomizer):
    mac_randomizer.generate()
    assert mac_randomizer.get_history() == []  # history only from randomize()


@pytest.mark.asyncio
async def test_mac_history_after_randomize(mac_randomizer):
    await mac_randomizer.randomize()
    await mac_randomizer.randomize()
    assert len(mac_randomizer.get_history()) == 2


# ── IP Anonymizer Tests ────────────────────────────────────────────────────────

def test_ip_initial_status(ip_anonymizer):
    status = ip_anonymizer.get_status()
    assert status["tor_active"] is False
    assert status["vpn_active"] is False
    assert status["ipv6_disabled"] is False


@pytest.mark.asyncio
async def test_enable_tor(ip_anonymizer):
    result = await ip_anonymizer.enable_tor()
    assert result is True
    assert ip_anonymizer._tor_active is True


@pytest.mark.asyncio
async def test_enable_vpn(ip_anonymizer):
    result = await ip_anonymizer.enable_vpn()
    assert result is True
    assert ip_anonymizer._vpn_active is True


@pytest.mark.asyncio
async def test_disable_ipv6(ip_anonymizer):
    result = await ip_anonymizer.disable_ipv6()
    assert result is True
    assert ip_anonymizer._ipv6_disabled is True


@pytest.mark.asyncio
async def test_full_anonymize(ip_anonymizer):
    results = await ip_anonymizer.full_anonymize()
    assert results["tor"] is True
    assert results["vpn"] is True
    assert results["ipv6_disabled"] is True
    assert results["dns_protected"] is True


@pytest.mark.asyncio
async def test_anonymization_level_maximum(ip_anonymizer):
    await ip_anonymizer.full_anonymize()
    status = ip_anonymizer.get_status()
    assert status["anonymization_level"] == "maximum"


# ── Trail Wipe Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wipe_quick(trail_wipe):
    report = await trail_wipe.wipe(WipeStandard.QUICK)
    assert report.success is True
    assert len(report.components_wiped) == len(TrailWipeEngine.WIPE_COMPONENTS)


@pytest.mark.asyncio
async def test_wipe_dod_3pass(trail_wipe):
    report = await trail_wipe.wipe(WipeStandard.DOD_3PASS)
    assert report.success is True
    assert report.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_panic_wipe(trail_wipe):
    report = await trail_wipe.panic_wipe()
    assert report.success is True
    assert report.standard == WipeStandard.DOD_7PASS
    assert report.is_clean is True


@pytest.mark.asyncio
async def test_wipe_specific_components(trail_wipe):
    report = await trail_wipe.wipe(
        WipeStandard.QUICK,
        components=["application_logs", "dns_cache"],
    )
    assert report.success is True
    assert len(report.components_wiped) == 2


def test_wipe_history(trail_wipe):
    assert trail_wipe.get_history() == []


@pytest.mark.asyncio
async def test_wipe_history_populated(trail_wipe):
    await trail_wipe.wipe(WipeStandard.QUICK)
    history = trail_wipe.get_history()
    assert len(history) == 1
    assert history[0]["success"] is True


# ── BLCKjACKArch Tests ─────────────────────────────────────────────────────────

def test_blckjack_initialization(blckjack):
    assert blckjack.anonymization_level == AnonymizationLevel.HIGH
    assert blckjack._initialized is False


@pytest.mark.asyncio
async def test_blckjack_initialize(blckjack):
    result = await blckjack.initialize()
    assert result["initialized"] is True
    assert "mac" in result
    assert blckjack._initialized is True


@pytest.mark.asyncio
async def test_blckjack_panic(blckjack):
    report = await blckjack.panic()
    assert report.success is True


def test_blckjack_status(blckjack):
    status = blckjack.get_status()
    assert status["codename"] == "BLCKjACK"
    assert "initialized" in status
    assert "anonymization_level" in status
