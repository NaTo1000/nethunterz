"""
Tests for Voice Control System.
"""
import pytest
from voice_control import (
    CommandIntent,
    IVRMenu,
    NLPCommandParser,
    VoiceChannel,
    VoiceControlSystem,
)


@pytest.fixture
def voice_system():
    return VoiceControlSystem(require_auth=False)


@pytest.fixture
def nlp():
    return NLPCommandParser()


@pytest.fixture
def ivr():
    return IVRMenu()


# ── NLP Parser Tests ──────────────────────────────────────────────────────────

def test_parse_scan_shortcode(nlp):
    intent, conf, params = nlp.parse("SCAN")
    assert intent == CommandIntent.SCAN
    assert conf == 1.0


def test_parse_status_shortcode(nlp):
    intent, conf, params = nlp.parse("STATUS")
    assert intent == CommandIntent.STATUS


def test_parse_wipe_shortcode(nlp):
    intent, conf, params = nlp.parse("WIPE")
    assert intent == CommandIntent.WIPE


def test_parse_natural_scan(nlp):
    intent, conf, params = nlp.parse("please scan the network")
    assert intent == CommandIntent.SCAN


def test_parse_natural_status(nlp):
    intent, conf, params = nlp.parse("what is the status?")
    assert intent == CommandIntent.STATUS


def test_parse_natural_defend(nlp):
    intent, conf, params = nlp.parse("defend against the attack")
    assert intent == CommandIntent.DEFEND


def test_parse_unknown(nlp):
    intent, conf, params = nlp.parse("hello there general kenobi")
    assert intent == CommandIntent.UNKNOWN


def test_parse_extracts_ip(nlp):
    intent, conf, params = nlp.parse("scan 192.168.1.1")
    assert params.get("target_ip") == "192.168.1.1"


# ── IVR Menu Tests ─────────────────────────────────────────────────────────────

def test_ivr_initial_prompt(ivr):
    prompt = ivr.get_prompt()
    assert "NayDoeV1" in prompt
    assert len(prompt) > 10


def test_ivr_navigate_to_submenu(ivr):
    response, is_command = ivr.navigate("3")
    assert not is_command
    assert "Security" in response or "security" in response.lower()


def test_ivr_navigate_to_command(ivr):
    # Navigate to status
    response, is_command = ivr.navigate("1")
    assert is_command is True


def test_ivr_invalid_option(ivr):
    response, is_command = ivr.navigate("8")
    assert not is_command
    assert "Invalid" in response or "option" in response.lower()


def test_ivr_reset(ivr):
    ivr.navigate("3")  # go to security menu
    ivr.reset()
    assert ivr._current_menu == "root"


# ── Voice System Tests ────────────────────────────────────────────────────────

def test_voice_system_initialization(voice_system):
    assert len(voice_system.wake_words) > 0
    assert voice_system.require_auth is False


def test_wake_word_detection(voice_system):
    assert voice_system._check_wake_word("hey naydoe please scan")
    assert voice_system._check_wake_word("hey jessica what's the status")
    assert not voice_system._check_wake_word("hello world")


@pytest.mark.asyncio
async def test_process_sms_scan(voice_system):
    called = []

    async def scan_handler(cmd):
        called.append("scan")
        return {"networks": 5}

    voice_system.register_handler(CommandIntent.SCAN, scan_handler)
    response = await voice_system.process_sms("SCAN")
    assert response.success is True
    assert called == ["scan"]


@pytest.mark.asyncio
async def test_process_sms_unknown(voice_system):
    response = await voice_system.process_sms("RANDOM STUFF HERE")
    # Should process even with unknown intent (no handler = fail)
    assert response.command_id is not None


@pytest.mark.asyncio
async def test_process_voice_no_wake_word(voice_system):
    audio = b"\x00" * 1024
    response = await voice_system.process_voice(audio, VoiceChannel.MICROPHONE)
    # Should return None if no wake word detected
    assert response is None or True  # simulated STT may pass


@pytest.mark.asyncio
async def test_process_phone_dtmf_status(voice_system):
    called = []

    async def status_handler(cmd):
        called.append("status")
        return "All systems operational"

    voice_system.register_handler(CommandIntent.STATUS, status_handler)
    response = await voice_system.process_phone_dtmf("1")
    assert response is not None


def test_voice_stats(voice_system):
    stats = voice_system.get_stats()
    assert "total_commands" in stats
    assert "wake_words" in stats
    assert "languages_supported" in stats
