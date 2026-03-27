"""
Flipper Zero Firmware Integration with NayDoeV1 80s GUI.

Full firmware integration featuring:
  - NayDoeV1 splash screens with typewriter font
  - 80s theme: Baywatch, Miami Vice, Night Rider, Bionic Man
  - Dolphin + NayDoeV1 bot animations
  - Rich color palette optimized for Flipper Zero display
  - Cloud filesystem self-installation
  - Minimal runtime footprint
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


# ─── Flipper Zero Color Palette ──────────────────────────────────────────────
# Flipper Zero has a monochrome 128x64 display, but we represent
# the theme colors for the companion app and simulator.
class FlipperColor(Enum):
    BLACK = "#000000"
    WHITE = "#FFFFFF"
    MIAMI_PINK = "#FF69B4"
    MIAMI_TEAL = "#00CED1"
    MIAMI_ORANGE = "#FF6347"
    BAYWATCH_RED = "#DC143C"
    BAYWATCH_GOLD = "#FFD700"
    NIGHTRIDER_BLACK = "#1A1A2E"
    NIGHTRIDER_BLUE = "#16213E"
    NIGHTRIDER_CYAN = "#00FFFF"
    BIONIC_SILVER = "#C0C0C0"
    BIONIC_GREEN = "#00FF41"
    NEON_PURPLE = "#9400D3"
    NEON_YELLOW = "#FFFF00"
    CRT_AMBER = "#FFB000"


# ─── 80s Theme Definitions ────────────────────────────────────────────────────
THEMES_80S = {
    "miami_vice": {
        "primary": FlipperColor.MIAMI_PINK,
        "secondary": FlipperColor.MIAMI_TEAL,
        "accent": FlipperColor.MIAMI_ORANGE,
        "background": FlipperColor.NIGHTRIDER_BLACK,
        "text": FlipperColor.WHITE,
        "tagline": "MIAMI VICE MODE ENGAGED",
    },
    "baywatch": {
        "primary": FlipperColor.BAYWATCH_RED,
        "secondary": FlipperColor.BAYWATCH_GOLD,
        "accent": FlipperColor.WHITE,
        "background": FlipperColor.BLACK,
        "text": FlipperColor.BAYWATCH_GOLD,
        "tagline": "RUNNING ON THE BEACH...",
    },
    "night_rider": {
        "primary": FlipperColor.NIGHTRIDER_CYAN,
        "secondary": FlipperColor.NIGHTRIDER_BLUE,
        "accent": FlipperColor.NEON_PURPLE,
        "background": FlipperColor.NIGHTRIDER_BLACK,
        "text": FlipperColor.NIGHTRIDER_CYAN,
        "tagline": "K.I.T.T. ONLINE",
    },
    "bionic_man": {
        "primary": FlipperColor.BIONIC_SILVER,
        "secondary": FlipperColor.BIONIC_GREEN,
        "accent": FlipperColor.NEON_YELLOW,
        "background": FlipperColor.BLACK,
        "text": FlipperColor.BIONIC_GREEN,
        "tagline": "WE CAN REBUILD IT",
    },
    "naydoe_default": {
        "primary": FlipperColor.NEON_PURPLE,
        "secondary": FlipperColor.BIONIC_GREEN,
        "accent": FlipperColor.CRT_AMBER,
        "background": FlipperColor.NIGHTRIDER_BLACK,
        "text": FlipperColor.BIONIC_GREEN,
        "tagline": "NayDoeV1 ONLINE",
    },
}


# ─── ASCII Art Frames ─────────────────────────────────────────────────────────
DOLPHIN_FRAMES = [
    # Frame 1 - Dolphin swimming right
    r"""
  _____
 /     \___
|  o    \  \__
 \_____/
""",
    # Frame 2 - Dolphin jumping
    r"""
       _____
      /     \
  ___/  o   |
 /___\___/
""",
    # Frame 3 - Dolphin with NayDoeV1 bot
    r"""
  ___  /\
 /   \/  |
| NaY|   /
 \___\__/
""",
]

NAYDOE_BOT_FRAMES = [
    # Frame 1 - Bot standing
    r"""
  [NaY]
  |o o|
  | _ |
  |___|
 /|   |\
""",
    # Frame 2 - Bot waving
    r"""
  [NaY]
  |o o|  /
  | _ | /
  |___|
   | |
""",
    # Frame 3 - Bot hacking
    r"""
  [NaY]
  |> <|
  | _ |  [HACK]
  |___|--[====]
   | |
""",
]

SPLASH_SCREENS = {
    "boot": """
╔══════════════════════════════════════╗
║  ███╗   ██╗ █████╗ ██╗   ██╗        ║
║  ████╗  ██║██╔══██╗╚██╗ ██╔╝        ║
║  ██╔██╗ ██║███████║ ╚████╔╝         ║
║  ██║╚██╗██║██╔══██║  ╚██╔╝          ║
║  ██║ ╚████║██║  ██║   ██║           ║
║  ╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝          ║
║         D O E  V 1                   ║
║                                      ║
║  PINEAPPLE PAGER v1.0  [FLIPPER]    ║
║  ────────────────────────────────   ║
║  > Initializing AI subsystems...    ║
║  > Loading PineDAP modules...       ║
║  > Activating NayDoeV1...          ║
╚══════════════════════════════════════╝
""",
    "miami_vice": """
╔══════════════════════════════════════╗
║  ░░░M░░I░░A░░M░░I░░ ░░V░░I░░C░░E░░ ║
║  ┌────────────────────────────────┐ ║
║  │   ~  ~  ≈  ~  ~  ≈  ~  ~  ≈  │ ║
║  │  SOUTH BEACH RECON ACTIVE      │ ║
║  │  [============================]│ ║
║  └────────────────────────────────┘ ║
║  JessicAi: "Looking good, partner" ║
╚══════════════════════════════════════╝
""",
    "night_rider": """
╔══════════════════════════════════════╗
║  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ ║
║  ░░░N░░I░░G░░H░░T░░ R░░I░░D░░E░░R░ ║
║         [K.I.T.T.]                  ║
║    _______________                  ║
║   |  ●  ●  ●  ●  |  ← ← ←         ║
║   |_______________|                 ║
║  NayDoeV1: "Scanning frequencies"  ║
╚══════════════════════════════════════╝
""",
    "baywatch": """
╔══════════════════════════════════════╗
║  🏖  B A Y W A T C H  M O D E  🏖  ║
║  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   ║
║  ~~~~ RUNNING ON THE BEACH ~~~~     ║
║  [RED_ALERT: Network compromised]   ║
║  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   ║
║  JessicAi: "Alert! Initiating..."  ║
╚══════════════════════════════════════╝
""",
    "bionic": """
╔══════════════════════════════════════╗
║   B I O N I C   M A N   M O D E    ║
║  ┌──────────────────────────────┐   ║
║  │  NEURAL LINK: ████████ 100% │   ║
║  │  SERVO POWER: ████████  98% │   ║
║  │  AI SYNC:     ████████ 100% │   ║
║  └──────────────────────────────┘   ║
║  "We have the technology."          ║
╚══════════════════════════════════════╝
""",
}

TYPEWRITER_MESSAGES = [
    "INITIALIZING NAYDOEV1 CONDUCTOR...",
    "LOADING PINEDAP MODULES...",
    "ESTABLISHING ENCRYPTED CHANNELS...",
    "AI SUBSYSTEMS: ONLINE",
    "CHAIMERA ENGINE: READY",
    "TWINBRAIN ALGORITHM: SYNCHRONIZED",
    "BLOCKCHAIN MEMORY: ACTIVE",
    "VOICE CONTROL: LISTENING...",
    "TRAIL WIPE: ARMED",
    "ALL SYSTEMS NOMINAL. READY FOR OPERATIONS.",
]


class FlipperScreen(Enum):
    SPLASH = "splash"
    DASHBOARD = "dashboard"
    OPERATIONS = "operations"
    CHAT = "chat"
    VOICE = "voice"
    SETTINGS = "settings"
    ANIMATION = "animation"
    NETWORK_MAP = "network_map"


@dataclass
class FlipperDisplayState:
    """Current state of the Flipper Zero display."""
    screen: FlipperScreen = FlipperScreen.SPLASH
    theme: str = "naydoe_default"
    content: str = ""
    animation_frame: int = 0
    brightness: int = 100
    typewriter_pos: int = 0
    typewriter_text: str = ""
    status_bar: str = ""
    timestamp: float = field(default_factory=time.time)


class TypewriterEffect:
    """Typewriter text animation for the splash screens."""

    def __init__(self, speed_ms: int = 50) -> None:
        self.speed_ms = speed_ms
        self._buffer = ""
        self._target = ""

    def set_text(self, text: str) -> None:
        self._target = text
        self._buffer = ""

    async def tick(self) -> str:
        """Advance one character. Returns current visible text."""
        if len(self._buffer) < len(self._target):
            self._buffer += self._target[len(self._buffer)]
            await asyncio.sleep(self.speed_ms / 1000)
        return self._buffer

    async def animate_full(self) -> str:
        """Animate full text. Returns complete text when done."""
        while len(self._buffer) < len(self._target):
            await self.tick()
        return self._buffer

    @property
    def is_complete(self) -> bool:
        return self._buffer == self._target


class FlipperAnimation:
    """Animation engine for Flipper Zero display."""

    def __init__(self) -> None:
        self._frame = 0
        self._running = False

    async def play_boot_sequence(self) -> List[str]:
        """Play the full NayDoeV1 boot animation."""
        frames = []

        # Dolphin swim animation
        for dolphin_frame in DOLPHIN_FRAMES:
            frames.append(dolphin_frame)
            await asyncio.sleep(0.1)

        # NayDoeV1 bot appears
        for bot_frame in NAYDOE_BOT_FRAMES:
            frames.append(bot_frame)
            await asyncio.sleep(0.1)

        # Splash screen
        frames.append(SPLASH_SCREENS["boot"])

        # Typewriter messages
        tw = TypewriterEffect(speed_ms=30)
        for msg in TYPEWRITER_MESSAGES:
            tw.set_text(msg)
            await tw.animate_full()
            frames.append(f"\n> {tw._buffer}")
            await asyncio.sleep(0.2)

        return frames

    async def play_theme(self, theme_name: str) -> str:
        """Play a specific 80s theme intro animation."""
        if theme_name == "miami_vice":
            return SPLASH_SCREENS["miami_vice"]
        elif theme_name == "night_rider":
            return SPLASH_SCREENS["night_rider"]
        elif theme_name == "baywatch":
            return SPLASH_SCREENS["baywatch"]
        elif theme_name == "bionic_man":
            return SPLASH_SCREENS["bionic"]
        else:
            return SPLASH_SCREENS["boot"]


class FlipperOperationsGUI:
    """
    Flipper Zero operations dashboard GUI.

    Displays all 100 autonomous operations with real-time status,
    NayDoeV1 80s styling, and voice activity indicators.
    """

    def __init__(self, theme: str = "naydoe_default") -> None:
        self.theme = theme
        self._display = FlipperDisplayState(theme=theme)
        self._operations_status: Dict[str, Any] = {}

    def render_dashboard(
        self,
        system_status: Dict[str, Any],
    ) -> str:
        """Render the main operations dashboard."""
        theme_cfg = THEMES_80S.get(self.theme, THEMES_80S["naydoe_default"])
        tagline = theme_cfg["tagline"]

        uptime = system_status.get("uptime_seconds", 0)
        h, m, s = int(uptime // 3600), int((uptime % 3600) // 60), int(uptime % 60)

        ai_status = "ONLINE" if system_status.get("ai_enabled") else "OFFLINE"
        voice_status = "ON" if system_status.get("voice_control") else "OFF"
        lines = [
            "╔══ NayDoeV1 OPERATIONS ══════════════════╗",
            f"║ {tagline:<39}║",
            "║ ─────────────────────────────────────── ║",
            f"║ Uptime: {h:02d}:{m:02d}:{s:02d}                           ║",
            f"║ AI: {ai_status:<5}  Voice: {voice_status:<4}          ║",
            "║ ─────────────────────────────────────── ║",
        ]

        # Operations summary
        autonomy = system_status.get("autonomy_stats", {})
        total = autonomy.get("total_operations_registered", 0)
        runs = autonomy.get("total_runs", 0)
        ok = autonomy.get("successful_runs", 0)

        lines.append(f"║ Ops: {total} registered | {runs} runs | {ok} ok     ║")

        # PineDAP
        pd = system_status.get("pinedap", {})
        active_mods = sum(
            1 for m in pd.get("modules", {}).values()
            if m.get("status") == "active"
        )
        lines.append(f"║ PineDAP: {active_mods} modules active                 ║")
        lines.append("╚════════════════════════════════════════╝")

        return "\n".join(lines)

    def render_network_map(
        self,
        networks: List[Dict[str, Any]],
    ) -> str:
        """Render a simplified network map."""
        lines = ["╔══ NETWORK MAP ══════════════════════════╗"]
        for i, net in enumerate(networks[:8]):  # max 8 visible
            ssid = net.get("ssid", "???")[:16]
            signal = net.get("signal_dbm", -90)
            bars = "▓" * max(1, (signal + 100) // 15)
            lines.append(f"║ {i+1}. {ssid:<16} {bars:<10}     ║")
        lines.append("╚════════════════════════════════════════╝")
        return "\n".join(lines)

    def render_voice_indicator(self, listening: bool, text: str = "") -> str:
        """Render voice activity indicator."""
        indicator = "●" if listening else "○"
        wave = "~~~≈≈≈~~~" if listening else "─────────"
        return (
            f"[VOICE {indicator}] {wave}\n"
            f"{text[:40] if text else 'Say \"Hey NayDoe\" to activate...'}"
        )

    def render_device_constellation(
        self,
        devices: Dict[str, bool],
    ) -> str:
        """Render connected devices view."""
        lines = ["╔══ DEVICE CONSTELLATION ════════════════╗"]
        device_icons = {
            "pineapple_pager": "🍍",
            "flipper_zero": "🐬",
            "esp32": "📡",
            "lora_node": "📻",
            "iphone": "📱",
        }
        for device, online in devices.items():
            icon = device_icons.get(device, "•")
            status = "ONLINE" if online else "OFFLINE"
            lines.append(f"║ {icon} {device:<18} [{status}]   ║")
        lines.append("╚════════════════════════════════════════╝")
        return "\n".join(lines)


class FlipperZeroFirmware:
    """
    Flipper Zero Firmware Integration.

    Full GUI with NayDoeV1 80s-themed styling and cloud sync.
    Maintains minimal runtime footprint on the Flipper device.
    """

    FIRMWARE_VERSION = "1.0.0"
    CODENAME = "NAYDOE_FLIPPER"

    def __init__(
        self,
        theme: str = "naydoe_default",
        cloud_filesystem=None,
    ) -> None:
        self.theme = theme
        self.cloud = cloud_filesystem
        self.gui = FlipperOperationsGUI(theme=theme)
        self.animation = FlipperAnimation()
        self._started = False
        self._start_time: Optional[float] = None
        self._pager_connection: Optional[Any] = None

    async def boot(self) -> List[str]:
        """Run full boot sequence with animations."""
        self._start_time = time.time()
        logger.info(f"[Flipper] Booting NayDoe Firmware v{self.FIRMWARE_VERSION}")

        # Play boot animation
        frames = await self.animation.play_boot_sequence()

        # Play theme intro
        theme_frame = await self.animation.play_theme(self.theme)
        frames.append(theme_frame)

        self._started = True
        logger.info("[Flipper] Boot complete")
        return frames

    async def install_cloud_filesystem(self) -> bool:
        """Install cloud filesystem from Flipper."""
        if not self.cloud:
            logger.warning("[Flipper] No cloud provider configured")
            return False

        await self.cloud.connect()
        result = await self.cloud.install()
        logger.info(f"[Flipper] Cloud filesystem installed: {result}")
        return result

    def render_current_screen(
        self,
        screen: FlipperScreen,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Render the current screen state."""
        data = data or {}

        if screen == FlipperScreen.SPLASH:
            return SPLASH_SCREENS["boot"]
        elif screen == FlipperScreen.DASHBOARD:
            return self.gui.render_dashboard(data)
        elif screen == FlipperScreen.NETWORK_MAP:
            return self.gui.render_network_map(data.get("networks", []))
        elif screen == FlipperScreen.VOICE:
            return self.gui.render_voice_indicator(
                data.get("listening", False),
                data.get("text", ""),
            )
        else:
            return SPLASH_SCREENS["boot"]

    def switch_theme(self, theme_name: str) -> bool:
        """Switch to a different 80s theme."""
        if theme_name in THEMES_80S:
            self.theme = theme_name
            self.gui.theme = theme_name
            logger.info(f"[Flipper] Theme switched: {theme_name}")
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        uptime = (time.time() - self._start_time) if self._start_time else 0
        return {
            "firmware_version": self.FIRMWARE_VERSION,
            "started": self._started,
            "theme": self.theme,
            "uptime_seconds": uptime,
            "cloud_connected": self.cloud is not None,
            "available_themes": list(THEMES_80S.keys()),
        }
