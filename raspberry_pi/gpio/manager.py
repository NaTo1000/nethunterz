"""Raspberry Pi 5 GPIO manager — real-time pin assignment and management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class GPIOMode(str, Enum):
    """GPIO pin operating mode."""

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    PWM = "PWM"
    I2C = "I2C"
    SPI = "SPI"
    UART = "UART"


class GPIOFunction(str, Enum):
    """Assigned function for a GPIO pin."""

    DEVICE_DETECT = "DEVICE_DETECT"
    POWER_MANAGEMENT = "POWER_MANAGEMENT"
    TRIGGER_INPUT = "TRIGGER_INPUT"
    LORA_GATEWAY = "LORA_GATEWAY"
    BLE_CONTROL = "BLE_CONTROL"
    FLIPPER_SYNC = "FLIPPER_SYNC"
    PAGER_SYNC = "PAGER_SYNC"
    STATUS_LED = "STATUS_LED"
    RESET = "RESET"
    UNASSIGNED = "UNASSIGNED"


@dataclass
class GPIOPin:
    """Represents a single GPIO pin on Raspberry Pi 5."""

    pin_number: int
    mode: GPIOMode = GPIOMode.INPUT
    function: GPIOFunction = GPIOFunction.UNASSIGNED
    device_label: Optional[str] = None
    current_state: int = 0  # 0=LOW, 1=HIGH
    pwm_frequency: Optional[float] = None  # Hz, only for PWM mode
    callbacks: List[Callable] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pin_number": self.pin_number,
            "mode": self.mode.value,
            "function": self.function.value,
            "device_label": self.device_label,
            "current_state": self.current_state,
            "pwm_frequency": self.pwm_frequency,
        }


@dataclass
class GPIOPinAssignment:
    """Assignment record for a GPIO pin."""

    pin_number: int
    function: GPIOFunction
    device_label: str
    mode: GPIOMode


# Raspberry Pi 5 has 40-pin header; BCM pins 0–27 are accessible
_VALID_BCM_PINS = set(range(2, 28))  # BCM 2–27 (excluding power/ground)


class GPIOManager:
    """
    Manages GPIO pins on the Raspberry Pi 5.

    Provides real-time pin assignment, state monitoring, and
    event-driven callbacks without requiring physical hardware
    (simulation mode when RPi.GPIO is not available).
    """

    def __init__(self, simulate: bool = True) -> None:
        self._simulate = simulate
        self._pins: Dict[int, GPIOPin] = {}
        self._assignments: List[GPIOPinAssignment] = []
        self._event_log: List[dict] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Initialise all valid BCM pins
        for bcm in _VALID_BCM_PINS:
            self._pins[bcm] = GPIOPin(pin_number=bcm)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_pin(
        self,
        pin: int,
        mode: GPIOMode,
        function: GPIOFunction = GPIOFunction.UNASSIGNED,
        device_label: Optional[str] = None,
    ) -> GPIOPin:
        """Configure a GPIO pin."""
        if pin not in _VALID_BCM_PINS:
            raise ValueError(f"BCM pin {pin} is not a valid GPIO pin on Raspberry Pi 5")
        gpio_pin = self._pins[pin]
        gpio_pin.mode = mode
        gpio_pin.function = function
        gpio_pin.device_label = device_label
        if function != GPIOFunction.UNASSIGNED:
            self._assignments.append(
                GPIOPinAssignment(
                    pin_number=pin,
                    function=function,
                    device_label=device_label or "",
                    mode=mode,
                )
            )
        return gpio_pin

    def assign_device_pin(
        self,
        pin: int,
        function: GPIOFunction,
        device_label: str,
        mode: GPIOMode = GPIOMode.OUTPUT,
    ) -> GPIOPinAssignment:
        """Assign a GPIO pin to a specific device and function."""
        self.setup_pin(pin, mode, function, device_label)
        assignment = GPIOPinAssignment(
            pin_number=pin,
            function=function,
            device_label=device_label,
            mode=mode,
        )
        return assignment

    # ------------------------------------------------------------------
    # Default layout for NetHunterz stack
    # ------------------------------------------------------------------

    def apply_nethunterz_layout(self) -> Dict[str, GPIOPinAssignment]:
        """
        Apply the default NetHunterz GPIO layout for Pi 5.

        Returns a mapping of device → assignment.
        """
        layout = {
            "flipper_sync": self.assign_device_pin(
                4, GPIOFunction.FLIPPER_SYNC, "flipper_zero", GPIOMode.OUTPUT
            ),
            "pager_sync": self.assign_device_pin(
                17, GPIOFunction.PAGER_SYNC, "pineapple_pager", GPIOMode.OUTPUT
            ),
            "lora_gateway": self.assign_device_pin(
                18, GPIOFunction.LORA_GATEWAY, "lora_module", GPIOMode.SPI
            ),
            "ble_control": self.assign_device_pin(
                27, GPIOFunction.BLE_CONTROL, "ble_adapter", GPIOMode.OUTPUT
            ),
            "device_detect_flipper": self.assign_device_pin(
                22, GPIOFunction.DEVICE_DETECT, "flipper_zero_detect", GPIOMode.INPUT
            ),
            "device_detect_pager": self.assign_device_pin(
                23, GPIOFunction.DEVICE_DETECT, "pager_detect", GPIOMode.INPUT
            ),
            "power_flipper": self.assign_device_pin(
                24, GPIOFunction.POWER_MANAGEMENT, "flipper_power", GPIOMode.OUTPUT
            ),
            "power_pager": self.assign_device_pin(
                25, GPIOFunction.POWER_MANAGEMENT, "pager_power", GPIOMode.OUTPUT
            ),
            "status_led": self.assign_device_pin(
                11, GPIOFunction.STATUS_LED, "system_status", GPIOMode.OUTPUT
            ),
            "trigger_input": self.assign_device_pin(
                8, GPIOFunction.TRIGGER_INPUT, "physical_trigger", GPIOMode.INPUT
            ),
        }
        return layout

    # ------------------------------------------------------------------
    # State control
    # ------------------------------------------------------------------

    def write_pin(self, pin: int, state: int) -> None:
        """Write HIGH (1) or LOW (0) to an output pin."""
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured")
        gpio_pin = self._pins[pin]
        if gpio_pin.mode not in (GPIOMode.OUTPUT, GPIOMode.PWM):
            raise ValueError(f"Pin {pin} is not an output pin")
        gpio_pin.current_state = state
        self._log_event("write", pin, state)
        for cb in gpio_pin.callbacks:
            try:
                cb(pin, state)
            except Exception:
                pass

    def read_pin(self, pin: int) -> int:
        """Read current state of a pin."""
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured")
        return self._pins[pin].current_state

    def add_callback(self, pin: int, callback: Callable) -> None:
        """Register a state-change callback on a pin."""
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured")
        self._pins[pin].callbacks.append(callback)

    # ------------------------------------------------------------------
    # Power management shortcuts
    # ------------------------------------------------------------------

    def power_on_device(self, device_label: str) -> bool:
        """Turn on the power pin for a named device."""
        return self._set_device_power(device_label, 1)

    def power_off_device(self, device_label: str) -> bool:
        """Turn off the power pin for a named device."""
        return self._set_device_power(device_label, 0)

    def _set_device_power(self, device_label: str, state: int) -> bool:
        for pin_obj in self._pins.values():
            if (
                pin_obj.device_label == device_label
                and pin_obj.function == GPIOFunction.POWER_MANAGEMENT
            ):
                self.write_pin(pin_obj.pin_number, state)
                return True
        return False

    def detect_device(self, device_label: str) -> bool:
        """Check whether a device-detect pin reads HIGH."""
        for pin_obj in self._pins.values():
            if (
                pin_obj.device_label == device_label
                and pin_obj.function == GPIOFunction.DEVICE_DETECT
            ):
                return self.read_pin(pin_obj.pin_number) == 1
        return False

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    async def start_monitoring(self, poll_interval: float = 1.0) -> None:
        """Start async pin-state monitoring loop."""
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(poll_interval)
        )

    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, poll_interval: float) -> None:
        while self._running:
            await asyncio.sleep(poll_interval)
            # In simulation mode, fire callbacks for detect pins to simulate
            # device attach/detach events (no real hardware polling needed).

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_pin_status(self, pin: int) -> dict:
        """Return current status of a single pin."""
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured")
        return self._pins[pin].to_dict()

    def get_all_assignments(self) -> List[dict]:
        """Return all active pin assignments."""
        return [
            a.__dict__ for a in self._assignments
            # deduplicate by most-recent assignment
        ]

    def get_layout_summary(self) -> dict:
        """Return a human-readable GPIO layout summary."""
        assigned = {
            p.pin_number: p.to_dict()
            for p in self._pins.values()
            if p.function != GPIOFunction.UNASSIGNED
        }
        return {
            "total_pins": len(_VALID_BCM_PINS),
            "assigned_pins": len(assigned),
            "pins": assigned,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, pin: int, value: int) -> None:
        self._event_log.append(
            {"type": event_type, "pin": pin, "value": value}
        )

    def get_event_log(self) -> List[dict]:
        return list(self._event_log)
