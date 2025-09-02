import pytest
from unittest.mock import MagicMock

from mautrix.util.config import ConfigUpdateHelper

from wallingfordbot.config import Config
from tests.fixtures.config import create_mock_config


class TestConfig:
    
    def test_do_update_copies_all_sections(self):
        # Mock the required methods for BaseProxyConfig
        load = MagicMock()
        load_base = MagicMock()
        save = MagicMock()
        
        config = Config(load, load_base, save)
        helper = MagicMock(spec=ConfigUpdateHelper)
        
        config.do_update(helper)
        
        expected_calls = [
            "rooms", "users", "homeassistant", "activities", 
            "confirmation_emojis", "timing", "messages"
        ]
        
        assert helper.copy.call_count == len(expected_calls)
        for expected_call in expected_calls:
            helper.copy.assert_any_call(expected_call)

    def test_config_properties(self):
        """Test all config properties with mocked data."""
        load = MagicMock()
        load_base = MagicMock() 
        save = MagicMock()
        
        config = Config(load, load_base, save)
        config._data = create_mock_config()
        
        assert config.alex_private_room == "!alexroom:example.com"
        assert config.group_chat_room == "!grouproom:example.com"
        assert config.alex_user_id == "@alex:example.com"
        assert config.webhook_secret == "test-secret-123"
        
        activities = config.activities
        assert "lunch" in activities
        assert activities["lunch"]["emoji"] == "🍽️"
        
        emojis = config.confirmation_emojis
        assert "🏠" in emojis
        assert len(emojis) == 5
        
        timing = config.timing
        assert timing["lunch_time"] == "12:30"
        assert timing["work_end_time"] == "17:30"
        
        messages = config.messages
        assert "confirmation_request" in messages
        assert "lunch_reminder" in messages