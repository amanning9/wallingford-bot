from typing import Dict, Any


def create_mock_config() -> Dict[str, Any]:
    """Create a mock configuration for testing."""
    return {
        "rooms": {
            "alex_private": "!alexroom:example.com",
            "group_chat": "!grouproom:example.com"
        },
        "users": {
            "alex_user_id": "@alex:example.com"
        },
        "homeassistant": {
            "webhook_secret": "test-secret-123"
        },
        "activities": {
            "lunch": {
                "emoji": "🍽️",
                "text": "to go for lunch at 12:30",
                "response": "Great! Alex will join for lunch at 12:30."
            },
            "picnic_dinner": {
                "emoji": "🥪",
                "text": "a picnic dinner",
                "response": "Alex will go shopping on his way home for a picnic dinner!"
            },
            "pub_dinner": {
                "emoji": "🍺", 
                "text": "to meet at the pub for dinner",
                "response": "Sounds good! Alex will meet you at the pub for dinner."
            }
        },
        "confirmation_emojis": ["🏠", "🏢", "🕒", "🚗", "❓"],
        "timing": {
            "lunch_time": "12:30",
            "work_end_time": "17:30",
            "lunch_reminder_offset": 30,
            "evening_reminder_offset": 60
        },
        "messages": {
            "confirmation_request": "Alex is at the office! React with your availability:\n🏠 Free for all activities\n🏢 Busy evening, lunch only\n🕒 Busy all day\n🚗 Going home\n❓ Unsure\n\nThen confirm with 👍",
            "lunch_reminder": "Lunch reminder! It's {lunch_time} time.",
            "evening_reminder": "Evening plans: {evening_plans}"
        }
    }