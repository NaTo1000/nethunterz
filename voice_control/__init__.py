"""Voice Control package."""
from .voice_system import (
    CommandIntent,
    IVRMenu,
    NLPCommandParser,
    SpeakerVerification,
    SpeechToText,
    TextToSpeech,
    VoiceChannel,
    VoiceCommand,
    VoiceControlSystem,
    VoiceResponse,
)

__all__ = [
    "VoiceControlSystem",
    "VoiceCommand",
    "VoiceResponse",
    "VoiceChannel",
    "CommandIntent",
    "SpeechToText",
    "TextToSpeech",
    "NLPCommandParser",
    "IVRMenu",
    "SpeakerVerification",
]
