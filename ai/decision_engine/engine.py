#!/usr/bin/env python3
"""
engine.py - Python decision engine for Flipper Zero autonomous control.
Implements the same rule + ML hybrid logic as the Android DecisionEngine.java.
Used for offline evaluation, testing, and cloud-side decision making.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).parent / "rules.json"
CONFIDENCE_THRESHOLD = 0.75


@dataclass
class Decision:
    action:     str
    confidence: float
    source:     str  # 'rule' or 'ml'
    rule_id:    str  = ""
    params:     Dict[str, Any] = field(default_factory=dict)
    timestamp:  float = field(default_factory=time.time)

    def is_actionable(self) -> bool:
        return self.action != "NONE" and self.confidence >= CONFIDENCE_THRESHOLD

    def __str__(self) -> str:
        return (f"Decision(action={self.action}, confidence={self.confidence:.2f}, "
                f"source={self.source}, rule={self.rule_id})")


@dataclass
class Rule:
    id:         str
    condition:  str
    action:     str
    priority:   float
    enabled:    bool          = True
    params:     Dict[str, Any] = field(default_factory=dict)


class DecisionEngine:
    """
    Hybrid decision engine combining rule-based logic with ML inference.
    """

    def __init__(self, rules_path: Optional[Path] = None,
                 model_path: Optional[Path] = None):
        self.rules: List[Rule] = []
        self.model = None
        self.evaluation_count = 0
        self._load_rules(rules_path or RULES_PATH)
        if model_path:
            self._load_model(model_path)

    def _load_rules(self, rules_path: Path):
        """Load rules from JSON file."""
        if rules_path.exists():
            with open(rules_path) as f:
                raw = json.load(f)
            for r in raw:
                rule = Rule(
                    id=r["id"],
                    condition=r["condition"],
                    action=r["action"],
                    priority=r.get("priority", 0.5),
                    enabled=r.get("enabled", True),
                    params=r.get("params", {}),
                )
                self.rules.append(rule)
            logger.info(f"Loaded {len(self.rules)} rules from {rules_path}")
        else:
            logger.warning(f"Rules file not found: {rules_path}, using built-in rules")
            self._load_builtin_rules()

    def _load_builtin_rules(self):
        """Load hard-coded fallback rules."""
        self.rules = [
            Rule("r001", "flipper_not_connected", "CONNECT_FLIPPER",  0.90),
            Rule("r002", "flipper_idle",          "SEND_PING",        0.60),
            Rule("r003", "version_unknown",       "GET_VERSION",      0.70),
            Rule("r004", "periodic_check",        "CHECK_STORAGE",    0.40),
            Rule("r005", "connection_error",      "DISCONNECT",       0.95),
        ]

    def _load_model(self, model_path: Path):
        """Load TFLite model for ML inference."""
        try:
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=str(model_path))
            interpreter.allocate_tensors()
            self.model = interpreter
            logger.info(f"TFLite model loaded: {model_path}")
        except Exception as e:
            logger.warning(f"Could not load TFLite model: {e}")

    def evaluate(self, context: Dict[str, Any]) -> Decision:
        """
        Evaluate all rules against context and return the best decision.
        """
        self.evaluation_count += 1
        best = Decision("NONE", 0.0, "none", "")

        # Rule-based evaluation
        for rule in self.rules:
            if not rule.enabled:
                continue
            score = self._evaluate_condition(rule.condition, context)
            if score > 0 and score > best.confidence:
                best = Decision(
                    action=rule.action,
                    confidence=score,
                    source="rule",
                    rule_id=rule.id,
                    params=dict(rule.params),
                )

        # ML-based evaluation (if model is available)
        if self.model is not None:
            features = self._extract_features(context)
            ml_action, ml_confidence = self._run_inference(features)
            if ml_confidence > best.confidence + 0.1:
                best = Decision(
                    action=ml_action,
                    confidence=ml_confidence,
                    source="ml",
                    rule_id="ml_model",
                )

        logger.debug(f"Eval #{self.evaluation_count}: {best}")
        return best

    def _evaluate_condition(self, condition: str,
                             ctx: Dict[str, Any]) -> float:
        """Evaluate a named condition against context, returning score [0,1]."""
        connected = ctx.get("flipper_connected", False)
        decisions = ctx.get("decision_count", 0)

        if condition == "flipper_not_connected":
            return 0.9 if not connected else 0.0

        elif condition == "flipper_idle":
            return 0.6 if connected and decisions % 10 == 0 else 0.0

        elif condition == "version_unknown":
            has_version = "firmware_version" in ctx
            return 0.7 if connected and not has_version else 0.0

        elif condition == "periodic_check":
            return 0.4 if decisions > 0 and decisions % 30 == 0 else 0.0

        elif condition == "connection_error":
            return 0.2 if not connected and decisions > 5 else 0.0

        return 0.0

    def _extract_features(self, ctx: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from context dict."""
        from ai.models.flipper_control_model import ACTION_CLASSES, INPUT_DIM
        decisions = ctx.get("decision_count", 0)
        return np.array([
            1.0 if ctx.get("flipper_connected", False) else 0.0,
            {"NONE": 0.0, "USB": 0.33, "UART": 0.67, "BLUETOOTH": 1.0}.get(
                ctx.get("connection_type", "NONE"), 0.0),
            (time.time() % 86400) / 86400.0,
            decisions / (decisions + 1) if decisions > 0 else 0.0,
            1.0 if ctx.get("actions_taken", 0) > 0 else 0.0,
            ctx.get("system_state_idx", 0) / 4.0,
            np.random.random() * 0.1,
        ], dtype=np.float32)

    def _run_inference(self, features: np.ndarray):
        """Run TFLite inference and return (action, confidence)."""
        try:
            from ai.models.flipper_control_model import ACTION_CLASSES
            input_details  = self.model.get_input_details()
            output_details = self.model.get_output_details()

            self.model.set_tensor(input_details[0]['index'],
                                  features.reshape(1, -1))
            self.model.invoke()

            output = self.model.get_tensor(output_details[0]['index'])[0]
            best_idx  = int(np.argmax(output))
            confidence = float(output[best_idx])
            action     = ACTION_CLASSES[best_idx] if best_idx < len(ACTION_CLASSES) else "NONE"
            return action, confidence

        except Exception as e:
            logger.warning(f"ML inference failed: {e}")
            return "NONE", 0.0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    engine = DecisionEngine()

    # Test with various contexts
    test_cases = [
        {"flipper_connected": False, "decision_count": 0},
        {"flipper_connected": True,  "decision_count": 1},
        {"flipper_connected": True,  "decision_count": 10},
        {"flipper_connected": True,  "firmware_version": "1.2.3", "decision_count": 30},
    ]

    for ctx in test_cases:
        d = engine.evaluate(ctx)
        print(f"Context: {ctx}")
        print(f"  -> {d}")
        print()
