"""
Tests for Conversational AI Chat System.
"""
import pytest
from conversational_ai import (
    ChatMessage,
    ChatSession,
    ConversationalAISystem,
    JessicAiChatBot,
    MessageType,
    UserRole,
)


@pytest.fixture
def chat_system():
    return ConversationalAISystem()


@pytest.fixture
def session():
    s = ChatSession(title="Test Session")
    return s


def test_session_initialization(session):
    assert session.title == "Test Session"
    assert len(session.messages) == 0
    assert session.active is True


def test_session_add_message(session):
    msg = ChatMessage(
        session_id=session.session_id,
        content="Hello JessicAi",
        message_type=MessageType.USER,
    )
    session.add_message(msg)
    assert len(session.messages) == 1


def test_session_context_window(session):
    for i in range(25):
        session.add_message(ChatMessage(content=f"msg {i}"))
    ctx = session.get_context_window(20)
    assert len(ctx) == 20


def test_session_search(session):
    session.add_message(ChatMessage(content="scan the network"))
    session.add_message(ChatMessage(content="check status"))
    session.add_message(ChatMessage(content="network analysis"))

    results = session.search("network")
    assert len(results) == 2


def test_session_bookmarks(session):
    msg = ChatMessage(content="important insight", bookmarked=True)
    session.add_message(msg)
    session.add_message(ChatMessage(content="normal message"))

    bookmarks = session.get_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0].content == "important insight"


def test_chat_system_register_user(chat_system):
    chat_system.register_user("user1", "Alice", UserRole.OPERATOR)
    assert "user1" in chat_system._users


def test_chat_system_create_session(chat_system):
    session = chat_system.create_session(title="Op Session")
    assert session.session_id in chat_system._sessions
    assert session.title == "Op Session"


@pytest.mark.asyncio
async def test_send_message(chat_system):
    chat_system.register_user("op1", "Operator", UserRole.OPERATOR)
    session = chat_system.create_session("Test")

    ai_msg = await chat_system.send_message(
        session.session_id,
        "op1",
        "What is the status?",
    )
    assert ai_msg.message_type == MessageType.AI
    assert len(ai_msg.content) > 0


@pytest.mark.asyncio
async def test_send_message_with_device_state(chat_system):
    chat_system.register_user("op1", "Op")
    session = chat_system.create_session()
    device_state = {"uptime_seconds": 3600, "ai_enabled": True}

    ai_msg = await chat_system.send_message(
        session.session_id, "op1",
        "status report",
        device_state=device_state,
    )
    assert ai_msg.content is not None


@pytest.mark.asyncio
async def test_brainstorm_operation(chat_system):
    session = chat_system.create_session("Brainstorm")
    plan = await chat_system.brainstorm_operation(
        session.session_id,
        "Network security assessment",
        {"networks": 15},
    )
    assert "plan_id" in plan
    assert "phases" in plan
    assert len(plan["phases"]) > 0
    assert plan["objective"] == "Network security assessment"


@pytest.mark.asyncio
async def test_invalid_session_raises(chat_system):
    with pytest.raises(ValueError):
        await chat_system.send_message("nonexistent", "user", "hello")


def test_get_stats_empty(chat_system):
    stats = chat_system.get_stats()
    assert stats["total_sessions"] == 0
    assert stats["total_messages"] == 0


@pytest.mark.asyncio
async def test_get_stats_after_use(chat_system):
    chat_system.register_user("u1", "User")
    session = chat_system.create_session()
    await chat_system.send_message(session.session_id, "u1", "hello")
    stats = chat_system.get_stats()
    assert stats["total_sessions"] == 1
    assert stats["total_messages"] >= 2  # user + AI


def test_search_all_sessions(chat_system):
    session = chat_system.create_session()
    msg = ChatMessage(
        session_id=session.session_id,
        content="find the rogue AP",
    )
    session.add_message(msg)
    chat_system._sessions[session.session_id] = session

    results = chat_system.search_all_sessions("rogue")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_jessica_ai_rule_responses():
    bot = JessicAiChatBot()
    session = ChatSession()

    # Test scan response
    r = await bot.respond(session, "scan the network")
    assert len(r) > 0

    # Test status response
    r = await bot.respond(session, "what is the status")
    assert len(r) > 0

    # Test wipe response
    r = await bot.respond(session, "wipe all data")
    assert len(r) > 0
