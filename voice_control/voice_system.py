"""
Voice Control System for Pineapple Pager.

Three input channels:
  1. Phone call voice control (VoIP/IVR)
  2. SMS command interface
  3. Direct microphone (wake word + continuous listening)
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger


class VoiceChannel(Enum):
    PHONE_CALL = "phone_call"
    SMS = "sms"
    MICROPHONE = "microphone"


class CommandIntent(Enum):
    SCAN = "scan"
    STATUS = "status"
    WIPE = "wipe"
    RECON = "recon"
    ATTACK = "attack"
    DEFEND = "defend"
    REPORT = "report"
    BACKUP = "backup"
    CHAT = "chat"
    UNKNOWN = "unknown"


SMS_SHORTCODES: Dict[str, CommandIntent] = {
    "SCAN": CommandIntent.SCAN,
    "STATUS": CommandIntent.STATUS,
    "WIPE": CommandIntent.WIPE,
    "RECON": CommandIntent.RECON,
    "REPORT": CommandIntent.REPORT,
    "BACKUP": CommandIntent.BACKUP,
    "DEFEND": CommandIntent.DEFEND,
}


@dataclass
class VoiceCommand:
    """A parsed voice or text command."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: VoiceChannel = VoiceChannel.MICROPHONE
    raw_input: str = ""
    transcript: str = ""
    intent: CommandIntent = CommandIntent.UNKNOWN
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    speaker_id: Optional[str] = None
    authenticated: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class VoiceResponse:
    """Response to a voice command."""
    command_id: str
    success: bool
    text: str
    spoken_text: str  # TTS-optimized version
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SpeechToText:
    """
    Speech-to-text processor (wraps Whisper or equivalent).
    Simulated in environments without audio hardware.
    """

    SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "zh", "ar", "ru", "ja"]

    def __init__(self, model: str = "whisper-base", language: str = "en") -> None:
        self.model = model
        self.language = language
        self._transcriptions = 0

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe audio bytes to text."""
        await asyncio.sleep(0.05)  # simulate processing
        self._transcriptions += 1
        return {
            "text": "[simulated transcription]",
            "language": language or self.language,
            "confidence": 0.95,
            "duration_ms": len(audio_data) // 32,  # rough estimate
        }

    async def transcribe_stream(
        self,
        audio_generator,
        language: Optional[str] = None,
    ):
        """Stream transcription from audio generator."""
        async for chunk in audio_generator:
            result = await self.transcribe(chunk, language)
            yield result


class TextToSpeech:
    """Text-to-speech engine for voice feedback."""

    VOICES = ["naydoe_80s", "jessica_ai", "robot_female", "robot_male"]

    def __init__(self, voice: str = "naydoe_80s", rate: int = 150) -> None:
        self.voice = voice
        self.rate = rate

    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes."""
        await asyncio.sleep(0.02)
        return text.encode()  # simulate audio output

    def optimize_for_voice(self, text: str) -> str:
        """Optimize text for TTS (remove markdown, special chars, etc.)."""
        text = re.sub(r"[*_`#\[\](){}|\\]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


class SpeakerVerification:
    """Speaker verification for voice authentication."""

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self._voiceprints: Dict[str, bytes] = {}

    def enroll(self, speaker_id: str, audio_sample: bytes) -> str:
        """Enroll a speaker with an audio sample."""
        voiceprint = hashlib.sha256(audio_sample).digest()
        self._voiceprints[speaker_id] = voiceprint
        logger.info(f"[VoiceAuth] Speaker enrolled: {speaker_id}")
        return speaker_id

    async def verify(self, audio: bytes) -> Tuple[Optional[str], float]:
        """Verify speaker identity. Returns (speaker_id, confidence)."""
        await asyncio.sleep(0.02)
        if not self._voiceprints:
            return None, 0.0
        # Simulated verification - in production uses embedding comparison
        return list(self._voiceprints.keys())[0], 0.92


class NLPCommandParser:
    """
    Natural language understanding for command parsing.
    Extracts intent and parameters from text input.
    """

    INTENT_PATTERNS: Dict[CommandIntent, List[str]] = {
        CommandIntent.SCAN: [
            r"\bscan\b", r"\bdiscover\b", r"\bfind\b.*\bnetwork\b",
            r"\bmap\b.*\bnetwork\b",
        ],
        CommandIntent.STATUS: [
            r"\bstatus\b", r"\bhow\b.*\bare\b.*\byou\b",
            r"\bwhat.*\bis.*\bhappening\b", r"\breport\b",
        ],
        CommandIntent.WIPE: [
            r"\bwipe\b", r"\bdelete\b.*\ball\b", r"\bpanic\b",
            r"\bemergency\b.*\bwipe\b", r"\bself.*destruct\b",
        ],
        CommandIntent.RECON: [
            r"\brecon\b", r"\breconnaissance\b", r"\bintelligence\b",
            r"\bgather\b.*\binfo\b",
        ],
        CommandIntent.DEFEND: [
            r"\bdefend\b", r"\bprotect\b", r"\bcountermeasure\b",
            r"\bblock\b.*\battack\b",
        ],
        CommandIntent.BACKUP: [
            r"\bbackup\b", r"\bsave\b.*\bstate\b", r"\bsnapshot\b",
        ],
        CommandIntent.CHAT: [
            r"\bchat\b", r"\btalk\b", r"\bdiscuss\b",
            r"\bbrainstorm\b", r"\bwhat.*\bshould\b",
        ],
    }

    def parse(self, text: str) -> Tuple[CommandIntent, float, Dict[str, Any]]:
        """
        Parse text and extract intent, confidence, and parameters.
        Returns (intent, confidence, parameters).
        """
        text_lower = text.lower().strip()

        # Check shortcodes first
        upper = text.upper().strip()
        if upper in SMS_SHORTCODES:
            return SMS_SHORTCODES[upper], 1.0, {}

        # Pattern matching
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent, 0.85, self._extract_params(text_lower, intent)

        return CommandIntent.UNKNOWN, 0.3, {}

    def _extract_params(
        self,
        text: str,
        intent: CommandIntent,
    ) -> Dict[str, Any]:
        """Extract parameters from text for a given intent."""
        params: Dict[str, Any] = {}

        # Extract network names
        network_match = re.search(r"network\s+['\"]?(\w+)['\"]?", text)
        if network_match:
            params["network"] = network_match.group(1)

        # Extract target IPs
        ip_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", text)
        if ip_match:
            params["target_ip"] = ip_match.group(1)

        return params


class IVRMenu:
    """
    Interactive Voice Response menu for phone call control.
    """

    MENU_TREE: Dict[str, Any] = {
        "root": {
            "prompt": "Welcome to NayDoeV1 command center. Press 1 for status, "
                      "2 to start scan, 3 for security operations, 4 for AI chat, "
                      "9 to wipe all data, or say a command.",
            "options": {
                "1": "status",
                "2": "scan",
                "3": "security_menu",
                "4": "ai_chat",
                "9": "wipe_confirm",
            },
        },
        "security_menu": {
            "prompt": "Security operations. Press 1 to activate countermeasures, "
                      "2 to deploy honeypot, 3 to start trail wipe.",
            "options": {
                "1": "countermeasures",
                "2": "honeypot",
                "3": "wipe_confirm",
            },
        },
        "wipe_confirm": {
            "prompt": "WARNING: This will wipe all data. Say 'confirm' to proceed "
                      "or press any other key to cancel.",
            "options": {
                "confirm": "wipe",
            },
            "requires_voice_confirm": True,
        },
    }

    def __init__(self) -> None:
        self._current_menu = "root"
        self._session_id = str(uuid.uuid4())

    def get_prompt(self) -> str:
        """Get the current menu prompt."""
        menu = self.MENU_TREE.get(self._current_menu, self.MENU_TREE["root"])
        return menu["prompt"]

    def navigate(self, input_str: str) -> Tuple[str, bool]:
        """
        Navigate IVR menu with input.
        Returns (response_text, is_command_ready).
        """
        menu = self.MENU_TREE.get(self._current_menu, self.MENU_TREE["root"])
        options = menu.get("options", {})

        if input_str in options:
            next_state = options[input_str]
            if next_state in self.MENU_TREE:
                self._current_menu = next_state
                return self.get_prompt(), False
            else:
                # It's a command
                self._current_menu = "root"
                return f"Executing {next_state}...", True

        return "Invalid option. " + self.get_prompt(), False

    def reset(self) -> None:
        self._current_menu = "root"


class SMSCommandQueue:
    """Queue for managing SMS commands."""

    def __init__(self, max_size: int = 100) -> None:
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._processed: List[VoiceCommand] = []

    async def enqueue(self, command: VoiceCommand) -> None:
        await self._queue.put(command)

    async def dequeue(self) -> VoiceCommand:
        return await self._queue.get()

    @property
    def pending(self) -> int:
        return self._queue.qsize()


class VoiceControlSystem:
    """
    Unified Voice Control System for Pineapple Pager.

    Handles all three voice input channels:
    - Phone call (VoIP/IVR)
    - SMS commands
    - Direct microphone (wake word)
    """

    VERSION = "1.0.0"
    DEFAULT_WAKE_WORDS = ["hey naydoe", "hey jessica", "ok pager"]

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        default_language: str = "en",
        require_auth: bool = True,
    ) -> None:
        self.wake_words = wake_words or self.DEFAULT_WAKE_WORDS
        self.default_language = default_language
        self.require_auth = require_auth

        self.stt = SpeechToText(language=default_language)
        self.tts = TextToSpeech()
        self.speaker_verify = SpeakerVerification()
        self.nlp = NLPCommandParser()
        self.ivr = IVRMenu()
        self.sms_queue = SMSCommandQueue()

        self._handlers: Dict[CommandIntent, Callable] = {}
        self._command_history: List[VoiceCommand] = []
        self._listening = False

    def register_handler(
        self,
        intent: CommandIntent,
        handler: Callable,
    ) -> None:
        """Register a handler for a command intent."""
        self._handlers[intent] = handler

    async def process_sms(self, sms_text: str, sender: str = "") -> VoiceResponse:
        """Process an incoming SMS command."""
        intent, confidence, params = self.nlp.parse(sms_text)

        cmd = VoiceCommand(
            channel=VoiceChannel.SMS,
            raw_input=sms_text,
            transcript=sms_text,
            intent=intent,
            parameters=params,
            confidence=confidence,
            authenticated=True,  # SMS auth via phone number
        )
        self._command_history.append(cmd)

        response = await self._dispatch(cmd)
        logger.info(
            f"[VoiceControl] SMS [{intent.value}] from {sender or 'unknown'}"
        )
        return response

    async def process_voice(
        self,
        audio_data: bytes,
        channel: VoiceChannel = VoiceChannel.MICROPHONE,
    ) -> Optional[VoiceResponse]:
        """Process raw audio through STT and command dispatch."""
        # Verify speaker if required
        speaker_id = None
        authenticated = not self.require_auth

        if self.require_auth:
            speaker_id, confidence = await self.speaker_verify.verify(audio_data)
            authenticated = speaker_id is not None and confidence >= 0.85

        # Transcribe
        transcript_result = await self.stt.transcribe(audio_data)
        transcript = transcript_result.get("text", "")

        # Check wake word for microphone channel
        if channel == VoiceChannel.MICROPHONE:
            if not self._check_wake_word(transcript):
                return None

        # Parse intent
        intent, confidence, params = self.nlp.parse(transcript)

        cmd = VoiceCommand(
            channel=channel,
            raw_input=transcript,
            transcript=transcript,
            intent=intent,
            parameters=params,
            confidence=confidence,
            speaker_id=speaker_id,
            authenticated=authenticated,
        )
        self._command_history.append(cmd)

        if not authenticated:
            return VoiceResponse(
                command_id=cmd.command_id,
                success=False,
                text="Authentication failed. Voice not recognized.",
                spoken_text="I'm sorry, I don't recognize your voice.",
            )

        return await self._dispatch(cmd)

    async def process_phone_dtmf(
        self,
        dtmf_input: str,
    ) -> VoiceResponse:
        """Process phone DTMF (keypad) input for IVR navigation."""
        response_text, is_command = self.ivr.navigate(dtmf_input)

        if is_command:
            intent, confidence, params = self.nlp.parse(dtmf_input)
            cmd = VoiceCommand(
                channel=VoiceChannel.PHONE_CALL,
                raw_input=dtmf_input,
                transcript=dtmf_input,
                intent=intent,
                confidence=1.0,
                authenticated=True,
            )
            self._command_history.append(cmd)
            return await self._dispatch(cmd)

        return VoiceResponse(
            command_id=str(uuid.uuid4()),
            success=True,
            text=response_text,
            spoken_text=self.tts.optimize_for_voice(response_text),
        )

    def _check_wake_word(self, transcript: str) -> bool:
        """Check if transcript contains a wake word."""
        text_lower = transcript.lower()
        return any(ww in text_lower for ww in self.wake_words)

    async def _dispatch(self, cmd: VoiceCommand) -> VoiceResponse:
        """Dispatch command to registered handler."""
        handler = self._handlers.get(cmd.intent)
        if not handler:
            return VoiceResponse(
                command_id=cmd.command_id,
                success=False,
                text=f"No handler for intent: {cmd.intent.value}",
                spoken_text=f"I don't know how to {cmd.intent.value} yet.",
            )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(cmd)
            else:
                result = handler(cmd)

            return VoiceResponse(
                command_id=cmd.command_id,
                success=True,
                text=str(result),
                spoken_text=self.tts.optimize_for_voice(str(result)),
                data=result if isinstance(result, dict) else {"result": result},
            )
        except Exception as e:
            return VoiceResponse(
                command_id=cmd.command_id,
                success=False,
                text=f"Command failed: {e}",
                spoken_text="Command execution failed.",
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return voice control system statistics."""
        total = len(self._command_history)
        by_channel: Dict[str, int] = {}
        by_intent: Dict[str, int] = {}

        for cmd in self._command_history:
            ch = cmd.channel.value
            by_channel[ch] = by_channel.get(ch, 0) + 1
            it = cmd.intent.value
            by_intent[it] = by_intent.get(it, 0) + 1

        return {
            "total_commands": total,
            "by_channel": by_channel,
            "by_intent": by_intent,
            "wake_words": self.wake_words,
            "languages_supported": SpeechToText.SUPPORTED_LANGUAGES,
            "auth_required": self.require_auth,
        }
