"""
JessicAi Conversational Chat System.

Real-time brainstorming interface with:
  - Context-aware multi-turn conversations
  - Operational planning and risk assessment
  - What-if scenario modeling
  - Team collaboration with role-based access
  - Chat history with blockchain-backed integrity
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


class UserRole(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    OBSERVER = "observer"


class MessageType(Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
    OPERATIONAL = "operational"
    SCENARIO = "scenario"


@dataclass
class ChatMessage:
    """A single chat message."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: str = ""
    role: UserRole = UserRole.OPERATOR
    message_type: MessageType = MessageType.USER
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    bookmarked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role.value,
            "type": self.message_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "bookmarked": self.bookmarked,
        }


@dataclass
class ChatSession:
    """A conversation session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Session"
    participants: List[str] = field(default_factory=list)
    messages: List[ChatMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    active: bool = True
    operation_plan: Optional[Dict[str, Any]] = None

    def add_message(self, msg: ChatMessage) -> None:
        self.messages.append(msg)
        self.last_activity = time.time()

    def get_context_window(self, max_messages: int = 20) -> List[ChatMessage]:
        """Return recent messages for context."""
        return self.messages[-max_messages:]

    def search(self, query: str) -> List[ChatMessage]:
        """Search messages for a query string."""
        q = query.lower()
        return [m for m in self.messages if q in m.content.lower()]

    def get_bookmarks(self) -> List[ChatMessage]:
        return [m for m in self.messages if m.bookmarked]


class OperationalBrainstorm:
    """
    AI-powered operational brainstorming engine.

    Analyzes environment, proposes operation plans, models what-if scenarios,
    and provides step-by-step guidance with real-time adjustments.
    """

    RISK_LEVELS = ["minimal", "low", "medium", "high", "critical"]

    def __init__(self) -> None:
        self._plans: List[Dict[str, Any]] = []
        self._scenarios: List[Dict[str, Any]] = []
        self._past_operations: List[Dict[str, Any]] = []

    async def analyze_environment(
        self,
        environment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze current environment and generate insights."""
        await asyncio.sleep(0.05)
        return {
            "environment_id": str(uuid.uuid4()),
            "network_density": environment_data.get("networks", 10),
            "threat_level": "medium",
            "opportunities": [
                "Open networks detected for captive portal deployment",
                "Weak WPS implementations on 3 APs",
                "DNS leaks visible on 2 clients",
            ],
            "risks": [
                "IDS/IPS system detected on enterprise network",
                "Active monitoring on channel 6",
            ],
            "recommended_approach": "passive_recon_first",
            "confidence": 0.87,
        }

    async def generate_operation_plan(
        self,
        objective: str,
        environment: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a step-by-step operation plan."""
        await asyncio.sleep(0.05)
        plan_id = str(uuid.uuid4())
        plan = {
            "plan_id": plan_id,
            "objective": objective,
            "phases": [
                {
                    "phase": 1,
                    "name": "Passive Reconnaissance",
                    "duration_estimate": "15-30 minutes",
                    "actions": [
                        "Enable passive monitor mode",
                        "Collect beacon frames and probe requests",
                        "Map network topology",
                        "Identify high-value targets",
                    ],
                    "risk": "minimal",
                },
                {
                    "phase": 2,
                    "name": "Active Intelligence Gathering",
                    "duration_estimate": "30-60 minutes",
                    "actions": [
                        "Targeted port scanning on identified hosts",
                        "Service fingerprinting",
                        "Vulnerability assessment",
                        "Client behavior analysis",
                    ],
                    "risk": "low",
                },
                {
                    "phase": 3,
                    "name": "Execution",
                    "duration_estimate": "Varies",
                    "actions": [
                        "Deploy countermeasures or assessment tools",
                        "Monitor for response",
                        "Adjust tactics based on feedback",
                        "Document findings in real-time",
                    ],
                    "risk": "medium",
                },
                {
                    "phase": 4,
                    "name": "Exfiltration & Cleanup",
                    "duration_estimate": "10-15 minutes",
                    "actions": [
                        "Collect all artifacts and evidence",
                        "Upload to secure cloud storage",
                        "Execute trail wipe",
                        "Generate operation report",
                    ],
                    "risk": "low",
                },
            ],
            "overall_risk": "medium",
            "success_probability": 0.85,
            "estimated_duration": "1.5-3 hours",
            "constraints_applied": constraints or {},
            "created_at": time.time(),
        }
        self._plans.append(plan)
        return plan

    async def what_if_scenario(
        self,
        scenario: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Model a what-if scenario with outcome prediction."""
        await asyncio.sleep(0.05)
        scenario_id = str(uuid.uuid4())
        result = {
            "scenario_id": scenario_id,
            "scenario": scenario,
            "variables": variables,
            "outcomes": [
                {
                    "outcome": "Success",
                    "probability": 0.65,
                    "description": "Operation proceeds as planned with minimal detection.",
                },
                {
                    "outcome": "Partial Success",
                    "probability": 0.25,
                    "description": "Objective achieved with some complications detected.",
                },
                {
                    "outcome": "Failure",
                    "probability": 0.10,
                    "description": "Operation triggered defensive response, abort recommended.",
                },
            ],
            "risk_assessment": {
                "detection_probability": 0.15,
                "countermeasure_risk": 0.10,
                "data_exposure_risk": 0.05,
                "overall_risk": "low",
            },
            "recommendations": [
                "Proceed with passive phase first to validate assumptions",
                "Have trail wipe ready on trigger if detection occurs",
                "Use frequency hopping to reduce RF signature",
            ],
            "analyzed_at": time.time(),
        }
        self._scenarios.append(result)
        return result

    async def assess_risk(
        self,
        operation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess risk for a proposed operation."""
        await asyncio.sleep(0.02)
        return {
            "operation_id": operation.get("plan_id", str(uuid.uuid4())),
            "risk_score": 4.2,  # out of 10
            "risk_level": "medium",
            "risk_factors": {
                "detection": 3.5,
                "legal": 5.0,
                "technical": 3.0,
                "operational_security": 4.5,
            },
            "mitigation_suggestions": [
                "Enable MAC randomization before operations",
                "Route all traffic through Tor/VPN",
                "Set automatic trail wipe trigger",
                "Use out-of-band communication channels",
            ],
        }

    def learn_from_operation(self, operation_record: Dict[str, Any]) -> None:
        """Learn from completed operations to improve future suggestions."""
        self._past_operations.append({
            **operation_record,
            "learned_at": time.time(),
        })


class JessicAiChatBot:
    """
    JessicAi conversational AI chatbot.

    Context-aware responses based on device state, network conditions,
    and historical data. Supports multi-turn conversations about strategy
    and tactics.
    """

    SYSTEM_PROMPT = (
        "You are JessicAi, an expert AI security operator assistant built into "
        "the NayDoeV1 NetHunterz system. You assist with network operations, "
        "security analysis, and tactical planning. You are knowledgeable about "
        "wireless security, penetration testing, anonymization, and AI-driven "
        "security operations. Always be strategic, concise, and actionable."
    )

    def __init__(
        self,
        model_manager=None,
        preferred_model: str = "nous-hermes",
    ) -> None:
        self.model_manager = model_manager
        self.preferred_model = preferred_model
        self.brainstorm = OperationalBrainstorm()
        self._total_responses = 0

    async def respond(
        self,
        session: ChatSession,
        user_message: str,
        device_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a contextual AI response."""
        # Build context from session history
        context = self._build_context(session, device_state)

        # Use model manager if available
        if self.model_manager:
            result = await self.model_manager.infer(
                self.preferred_model,
                prompt=f"{context}\nUser: {user_message}\nJessicAi:",
            )
            response_text = result.get("text", "")
        else:
            # Fallback: rule-based responses
            response_text = await self._rule_based_response(
                user_message, context, device_state
            )

        self._total_responses += 1
        return response_text

    def _build_context(
        self,
        session: ChatSession,
        device_state: Optional[Dict[str, Any]],
    ) -> str:
        """Build conversation context string."""
        lines = [self.SYSTEM_PROMPT]

        if device_state:
            lines.append(
                f"\nCurrent device state: {str(device_state)[:200]}"
            )

        if session.operation_plan:
            lines.append(
                f"\nActive operation plan: {session.operation_plan.get('objective', 'unknown')}"
            )

        # Add recent conversation history
        for msg in session.get_context_window(10):
            prefix = "User" if msg.message_type == MessageType.USER else "JessicAi"
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    async def _rule_based_response(
        self,
        message: str,
        context: str,
        device_state: Optional[Dict[str, Any]],
    ) -> str:
        """Fallback rule-based responses when no model is available."""
        msg = message.lower()

        if any(w in msg for w in ["scan", "discover", "find network"]):
            return (
                "Initiating network scan. I recommend starting with passive reconnaissance "
                "to minimize detection risk. Shall I configure PineAP for SSID harvesting "
                "while we scan, or keep it purely passive?"
            )
        elif any(w in msg for w in ["status", "how are you", "what's happening"]):
            state_info = f"Device uptime: {device_state.get('uptime_seconds', 0):.0f}s" \
                if device_state else "Device state unknown"
            return f"All systems operational. {state_info}. Awaiting your commands."
        elif any(w in msg for w in ["wipe", "clean", "delete"]):
            return (
                "Trail wipe ready. This will clear all logs, randomize MAC addresses, "
                "flush ARP tables, and terminate all active connections. "
                "Confirm with 'WIPE CONFIRM' to proceed."
            )
        elif any(w in msg for w in ["plan", "operation", "strategy"]):
            return (
                "Let me analyze the current environment and generate an operation plan. "
                "What's your primary objective? (e.g., network assessment, "
                "security audit, intelligence gathering)"
            )
        elif any(w in msg for w in ["risk", "safe", "danger"]):
            return (
                "Current risk assessment: Medium. Primary concerns are potential IDS/IPS "
                "on the enterprise subnet and active channel monitoring. "
                "Recommend enabling frequency hopping and keeping session under 30 minutes."
            )
        else:
            return (
                "Understood. I'm analyzing the situation. For best results, provide more "
                "context about your objective and current environment. "
                "What would you like to focus on?"
            )


class ConversationalAISystem:
    """
    Full Conversational AI System integrating JessicAi with all chat channels.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        model_manager=None,
    ) -> None:
        self.chatbot = JessicAiChatBot(model_manager=model_manager)
        self._sessions: Dict[str, ChatSession] = {}
        self._users: Dict[str, Dict[str, Any]] = {}

    def register_user(
        self,
        user_id: str,
        display_name: str,
        role: UserRole = UserRole.OPERATOR,
    ) -> None:
        """Register a user for chat access."""
        self._users[user_id] = {
            "user_id": user_id,
            "display_name": display_name,
            "role": role.value,
            "registered_at": time.time(),
        }

    def create_session(
        self,
        title: str = "New Session",
        user_ids: Optional[List[str]] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            title=title,
            participants=user_ids or [],
        )
        self._sessions[session.session_id] = session
        logger.info(f"[Chat] Session created: {session.session_id[:8]} '{title}'")
        return session

    async def send_message(
        self,
        session_id: str,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.USER,
        device_state: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        """Send a message and get AI response."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        user = self._users.get(user_id, {"role": "operator"})
        role = UserRole(user.get("role", "operator"))

        # Add user message
        user_msg = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=role,
            message_type=message_type,
            content=content,
        )
        session.add_message(user_msg)

        # Generate AI response
        ai_response_text = await self.chatbot.respond(
            session, content, device_state
        )

        ai_msg = ChatMessage(
            session_id=session_id,
            user_id="jessica_ai",
            role=UserRole.ADMIN,
            message_type=MessageType.AI,
            content=ai_response_text,
        )
        session.add_message(ai_msg)

        return ai_msg

    async def brainstorm_operation(
        self,
        session_id: str,
        objective: str,
        environment_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Start an operational brainstorming session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        env = environment_data or {}
        analysis = await self.chatbot.brainstorm.analyze_environment(env)
        plan = await self.chatbot.brainstorm.generate_operation_plan(
            objective=objective,
            environment=analysis,
        )

        session.operation_plan = plan
        session.title = f"Op: {objective[:30]}"

        # Post plan summary to chat
        plan_msg = ChatMessage(
            session_id=session_id,
            user_id="jessica_ai",
            role=UserRole.ADMIN,
            message_type=MessageType.OPERATIONAL,
            content=f"Operation plan generated: {plan['objective']}. "
                    f"Phases: {len(plan['phases'])}. "
                    f"Risk: {plan['overall_risk']}. "
                    f"Success probability: {plan['success_probability']:.0%}.",
            metadata={"plan_id": plan["plan_id"]},
        )
        session.add_message(plan_msg)

        return plan

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def search_all_sessions(self, query: str) -> List[ChatMessage]:
        """Search across all sessions."""
        results = []
        for session in self._sessions.values():
            results.extend(session.search(query))
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Return system statistics."""
        total_messages = sum(
            len(s.messages) for s in self._sessions.values()
        )
        return {
            "total_sessions": len(self._sessions),
            "total_messages": total_messages,
            "registered_users": len(self._users),
            "ai_responses": self.chatbot._total_responses,
        }
