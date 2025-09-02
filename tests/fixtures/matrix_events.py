import uuid
from datetime import datetime
from typing import Dict, Any
from mautrix.types import (
    ReactionEvent, EventID, RoomID, UserID, EventContent, EventType,
    RelationType, ReactionEventContent, RelatesTo
)


def create_mock_reaction_event(
    sender: str = "@testuser:example.com",
    room_id: str = "!testroom:example.com", 
    emoji: str = "🍽️",
    target_event_id: str = "$event123:example.com",
    rel_type: RelationType = RelationType.ANNOTATION
) -> ReactionEvent:
    """Create a mock reaction event for testing."""
    event_id = f"${uuid.uuid4().hex}:example.com"
    
    relates_to = RelatesTo(
        rel_type=rel_type,
        event_id=EventID(target_event_id),
        key=emoji
    )
    
    content = ReactionEventContent(relates_to=relates_to)
    
    return ReactionEvent(
        event_id=EventID(event_id),
        room_id=RoomID(room_id),
        sender=UserID(sender),
        timestamp=int(datetime.now().timestamp() * 1000),
        content=content,
        type=EventType.REACTION
    )


def create_mock_session_data(
    session_id: str = None,
    date: str = None,
    alex_confirmation: str = None,
    confirmed: bool = False,
    group_message_id: str = None,
    lunch_reminder_sent: bool = False,
    evening_reminder_sent: bool = False
) -> Dict[str, Any]:
    """Create mock workflow session data."""
    if session_id is None:
        session_id = f"office-{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        'id': session_id,
        'date': date,
        'alex_confirmation': alex_confirmation,
        'confirmed': confirmed,
        'group_message_id': group_message_id,
        'created_at': datetime.now(),
        'lunch_reminder_sent': lunch_reminder_sent,
        'evening_reminder_sent': evening_reminder_sent
    }


def create_mock_activity_reaction(
    session_id: str,
    user_id: str = "@testuser:example.com",
    activity: str = "lunch",
    emoji: str = "🍽️"
) -> Dict[str, Any]:
    """Create mock activity reaction data."""
    return {
        'id': 1,
        'session_id': session_id,
        'user_id': user_id,
        'activity': activity,
        'emoji': emoji,
        'created_at': datetime.now()
    }


def create_mock_reminder_data(
    session_id: str,
    reminder_type: str = "lunch",
    scheduled_time: datetime = None,
    sent: bool = False
) -> Dict[str, Any]:
    """Create mock scheduled reminder data."""
    if scheduled_time is None:
        scheduled_time = datetime.now()
    
    return {
        'id': 1,
        'session_id': session_id,
        'reminder_type': reminder_type,
        'scheduled_time': scheduled_time,
        'sent': sent,
        'created_at': datetime.now()
    }