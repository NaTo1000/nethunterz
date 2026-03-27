# Voice Control Setup Guide

## Overview

The NetHunterz voice control system supports three input channels:
1. **Phone Call** — VoIP endpoint with IVR menu
2. **SMS** — Text commands with shortcodes and NLP
3. **Microphone** — Wake word + continuous listening

## Phone Call Voice Control

```python
from voice_control import VoiceControlSystem, CommandIntent, VoiceChannel

voice = VoiceControlSystem(require_auth=True)

# Register handlers for intents
voice.register_handler(CommandIntent.SCAN, scan_handler)
voice.register_handler(CommandIntent.STATUS, status_handler)
voice.register_handler(CommandIntent.WIPE, wipe_handler)

# Process DTMF (phone keypad input)
response = await voice.process_phone_dtmf("1")  # Option 1 = status
print(response.spoken_text)  # Will be read back via TTS
```

### IVR Menu Structure

```
Root Menu:
  [1] → Status
  [2] → Start Scan
  [3] → Security Operations Sub-menu
       [3][1] → Activate Countermeasures
       [3][2] → Deploy Honeypot
       [3][3] → Trail Wipe (requires voice confirmation)
  [4] → AI Chat
  [9] → Wipe All Data (requires confirmation)
```

## SMS Command Interface

```python
# Process incoming SMS
response = await voice.process_sms("SCAN", sender="+15551234567")
print(response.text)  # Operation result
```

### SMS Shortcodes

| Code | Action | Response |
|------|--------|----------|
| `SCAN` | Network scan | Scan results summary |
| `STATUS` | System status | Device health report |
| `WIPE` | Trail wipe | Wipe confirmation |
| `RECON` | Reconnaissance | Target intelligence |
| `REPORT` | Security report | PDF report URL |
| `BACKUP` | System snapshot | Backup hash |
| `DEFEND` | Countermeasures | Deployment status |

### Natural Language SMS

You can also send natural language commands:
- "scan the network around me"
- "what's the current threat level?"
- "activate defensive countermeasures now"
- "give me a full status report"

## Direct Microphone Control

```python
# Configure wake words
voice = VoiceControlSystem(
    wake_words=["hey naydoe", "hey jessica", "ok pager"],
    default_language="en",
    require_auth=True,
)

# Process audio chunk (from microphone stream)
response = await voice.process_voice(audio_bytes, VoiceChannel.MICROPHONE)
if response:
    print(response.text)
    # response.spoken_text for TTS playback
```

### Wake Words
- **"Hey NayDoe"** — Primary wake word
- **"Hey Jessica"** — Alternative wake word
- **"Ok Pager"** — Device-specific wake word

### Voice Commands (after wake word)

- "scan networks"
- "what's the status?"
- "activate countermeasures"
- "wipe trails"
- "generate security report"
- "start reconnaissance"
- "backup the system"

## Speaker Verification

```python
from voice_control import SpeakerVerification

sv = SpeakerVerification(threshold=0.85)

# Enroll authorized speaker
sv.enroll("operator_alice", alice_voice_sample_bytes)

# Verify speaker identity
speaker_id, confidence = await sv.verify(audio_sample)
if confidence >= 0.85:
    print(f"Authenticated: {speaker_id}")
```

## Multi-Language Support

Supported languages: EN, ES, FR, DE, ZH, AR, RU, JA

```python
voice = VoiceControlSystem(default_language="es")  # Spanish
```

## Statistics

```python
stats = voice.get_stats()
# {
#   "total_commands": 42,
#   "by_channel": {"microphone": 20, "sms": 15, "phone_call": 7},
#   "by_intent": {"scan": 10, "status": 8, ...},
#   "wake_words": ["hey naydoe", ...],
#   "auth_required": True,
# }
```
