import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from mautrix.types import EventType, RelationType, UserID, RoomID, EventID
from aiohttp.web import Request, Response

from wallingfordbot.bot import WallingfordBot
from wallingfordbot.config import Config
from tests.fixtures.matrix_events import (
    create_mock_reaction_event, 
    create_mock_session_data,
    create_mock_activity_reaction,
    create_mock_reminder_data
)
from tests.fixtures.config import create_mock_config


@pytest.fixture
def mock_bot():
    """Create a mock WallingfordBot instance."""
    with patch('wallingfordbot.bot.WallingfordBot.__init__', return_value=None):
        bot = WallingfordBot.__new__(WallingfordBot)
        bot.database = AsyncMock()
        bot.client = AsyncMock()
        bot.client.mxid = UserID("@wallingfordbot:example.com")
        bot.log = MagicMock()
        bot.reminder_task = None
        
        # Mock config
        bot.config = MagicMock()
        mock_config_data = create_mock_config()
        bot.config.alex_private_room = mock_config_data["rooms"]["alex_private"]
        bot.config.group_chat_room = mock_config_data["rooms"]["group_chat"]
        bot.config.alex_user_id = mock_config_data["users"]["alex_user_id"]
        bot.config.webhook_secret = mock_config_data["homeassistant"]["webhook_secret"]
        bot.config.activities = mock_config_data["activities"]
        bot.config.confirmation_emojis = mock_config_data["confirmation_emojis"]
        bot.config.timing = mock_config_data["timing"]
        bot.config.messages = mock_config_data["messages"]
        
        return bot


class TestWallingfordBot:
    
    @pytest.mark.asyncio
    async def test_start_creates_reminder_task(self, mock_bot):
        mock_bot.config.load_and_update = MagicMock()
        
        with patch('asyncio.create_task') as mock_create_task:
            await mock_bot.start()
            
            mock_bot.config.load_and_update.assert_called_once()
            mock_create_task.assert_called_once()
            assert mock_bot.log.info.called

    @pytest.mark.asyncio
    async def test_stop_cancels_reminder_task(self, mock_bot):
        mock_task = AsyncMock()
        mock_bot.reminder_task = mock_task
        
        await mock_bot.stop()
        
        mock_task.cancel.assert_called_once()
        assert mock_bot.log.info.called

    @pytest.mark.asyncio
    async def test_homeassistant_webhook_unauthorized_no_header(self, mock_bot):
        request = MagicMock(spec=Request)
        request.headers = {}
        
        response = await mock_bot.homeassistant_webhook(request)
        
        assert response.status == 401
        assert response.text == "Unauthorized"

    @pytest.mark.asyncio
    async def test_homeassistant_webhook_unauthorized_invalid_token(self, mock_bot):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer wrong-token"}
        
        response = await mock_bot.homeassistant_webhook(request)
        
        assert response.status == 401
        assert response.text == "Invalid token"

    @pytest.mark.asyncio
    async def test_homeassistant_webhook_success(self, mock_bot):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer test-secret-123"}
        request.json = AsyncMock(return_value={"test": False})
        
        with patch.object(mock_bot, 'start_office_workflow') as mock_start:
            response = await mock_bot.homeassistant_webhook(request)
            
            assert response.status == 200
            assert response.text == "OK"
            mock_start.assert_called_once_with(is_test=False)

    @pytest.mark.asyncio
    async def test_homeassistant_webhook_test_mode(self, mock_bot):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer test-secret-123"}
        request.json = AsyncMock(return_value={"test": True})
        
        with patch.object(mock_bot, 'start_office_workflow') as mock_start:
            response = await mock_bot.homeassistant_webhook(request)
            
            assert response.status == 200
            mock_start.assert_called_once_with(is_test=True)

    @pytest.mark.asyncio
    async def test_homeassistant_webhook_exception_handling(self, mock_bot):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer test-secret-123"}
        request.json = AsyncMock(side_effect=Exception("JSON parse error"))
        
        response = await mock_bot.homeassistant_webhook(request)
        
        assert response.status == 500
        assert response.text == "Internal Server Error"
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_office_workflow_new_session(self, mock_bot):
        mock_bot.database.fetchrow.return_value = None
        
        with patch.object(mock_bot, 'send_confirmation_request') as mock_send:
            await mock_bot.start_office_workflow()
            
            mock_bot.database.execute.assert_called()
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_office_workflow_existing_confirmed_session(self, mock_bot):
        session_data = create_mock_session_data(confirmed=True)
        mock_bot.database.fetchrow.return_value = session_data
        
        with patch.object(mock_bot, 'send_confirmation_request') as mock_send:
            await mock_bot.start_office_workflow()
            
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_office_workflow_existing_unconfirmed_session(self, mock_bot):
        session_data = create_mock_session_data(confirmed=False)
        mock_bot.database.fetchrow.return_value = session_data
        
        with patch.object(mock_bot, 'send_confirmation_request') as mock_send:
            await mock_bot.start_office_workflow()
            
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_office_workflow_test_mode_clears_existing(self, mock_bot):
        mock_bot.database.fetchrow.return_value = None
        
        with patch.object(mock_bot, 'send_confirmation_request') as mock_send:
            await mock_bot.start_office_workflow(is_test=True)
            
            # Should call execute 4 times: 3 deletes + 1 insert
            assert mock_bot.database.execute.call_count >= 4
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_confirmation_request(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        
        await mock_bot.send_confirmation_request("test-session")
        
        mock_bot.client.send_text.assert_called_once()
        # Should react with confirmation emojis + thumbs up
        expected_reactions = len(mock_bot.config.confirmation_emojis) + 1
        assert mock_bot.client.react.call_count == expected_reactions

    @pytest.mark.asyncio
    async def test_send_confirmation_request_send_failure(self, mock_bot):
        mock_bot.client.send_text.side_effect = Exception("Send failed")
        
        await mock_bot.send_confirmation_request("test-session")
        
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_confirmation_request_react_failure(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        mock_bot.client.react.side_effect = Exception("React failed")
        
        await mock_bot.send_confirmation_request("test-session")
        
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_reaction_ignores_non_annotation(self, mock_bot):
        event = create_mock_reaction_event(rel_type=RelationType.REFERENCE)
        
        with patch.object(mock_bot, 'handle_confirmation_reaction') as mock_confirm, \
             patch.object(mock_bot, 'handle_activity_reaction') as mock_activity:
            await mock_bot.handle_reaction(event)
            
            mock_confirm.assert_not_called()
            mock_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_reaction_event_decorator(self, mock_bot):
        event = create_mock_reaction_event()
        
        with patch.object(mock_bot, 'handle_reaction') as mock_handle:
            await mock_bot.handle_reaction_event(event)
            
            mock_handle.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_reaction_alex_confirmation(self, mock_bot):
        event = create_mock_reaction_event(
            sender="@alex:example.com",
            room_id="!alexroom:example.com"
        )
        
        with patch.object(mock_bot, 'handle_confirmation_reaction') as mock_confirm:
            await mock_bot.handle_reaction(event)
            
            mock_confirm.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_reaction_activity_reaction(self, mock_bot):
        event = create_mock_reaction_event(
            sender="@otheruser:example.com",
            room_id="!grouproom:example.com"
        )
        
        with patch.object(mock_bot, 'handle_activity_reaction') as mock_activity:
            await mock_bot.handle_reaction(event)
            
            mock_activity.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_confirmation_reaction_stores_choice(self, mock_bot):
        event = create_mock_reaction_event(emoji="🏠")
        session_data = create_mock_session_data()
        mock_bot.database.fetchrow.return_value = session_data
        
        await mock_bot.handle_confirmation_reaction(event)
        
        mock_bot.database.execute.assert_called_once()
        args = mock_bot.database.execute.call_args[0]
        assert args[1] == "🏠"  # alex_confirmation
        assert args[2] == False  # confirmed

    @pytest.mark.asyncio
    async def test_handle_confirmation_reaction_no_session(self, mock_bot):
        event = create_mock_reaction_event(emoji="🏠")
        mock_bot.database.fetchrow.return_value = None
        
        await mock_bot.handle_confirmation_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_confirmation_reaction_invalid_emoji(self, mock_bot):
        event = create_mock_reaction_event(emoji="🌮")  # Not a confirmation emoji
        
        await mock_bot.handle_confirmation_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_confirmation_reaction_thumbs_up_confirms(self, mock_bot):
        event = create_mock_reaction_event(emoji="👍")
        
        with patch.object(mock_bot, 'confirm_previous_reaction') as mock_confirm:
            await mock_bot.handle_confirmation_reaction(event)
            
            mock_confirm.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_confirm_previous_reaction_success(self, mock_bot):
        session_data = create_mock_session_data(alex_confirmation="🏠")
        mock_bot.database.fetchrow.return_value = session_data
        
        with patch.object(mock_bot, 'send_group_announcement') as mock_announce, \
             patch.object(mock_bot, 'schedule_reminders') as mock_schedule:
            
            event = create_mock_reaction_event(emoji="👍")
            await mock_bot.confirm_previous_reaction(event)
            
            mock_bot.database.execute.assert_called_once()
            mock_announce.assert_called_once()
            mock_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_previous_reaction_going_home_no_announcement(self, mock_bot):
        session_data = create_mock_session_data(alex_confirmation="🚗")
        mock_bot.database.fetchrow.return_value = session_data
        
        with patch.object(mock_bot, 'send_group_announcement') as mock_announce:
            event = create_mock_reaction_event(emoji="👍")
            await mock_bot.confirm_previous_reaction(event)
            
            mock_announce.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_previous_reaction_no_session(self, mock_bot):
        mock_bot.database.fetchrow.return_value = None
        
        event = create_mock_reaction_event(emoji="👍")
        await mock_bot.confirm_previous_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_previous_reaction_no_confirmation(self, mock_bot):
        session_data = create_mock_session_data(alex_confirmation=None)
        mock_bot.database.fetchrow.return_value = session_data
        
        event = create_mock_reaction_event(emoji="👍")
        await mock_bot.confirm_previous_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_ignores_bot_reactions(self, mock_bot):
        event = create_mock_reaction_event(sender="@wallingfordbot:example.com")
        mock_bot.client.mxid = UserID("@wallingfordbot:example.com")
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_wrong_room(self, mock_bot):
        event = create_mock_reaction_event(room_id="!wrongroom:example.com")
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_non_annotation_relation(self, mock_bot):
        event = create_mock_reaction_event(
            room_id="!grouproom:example.com",
            rel_type=RelationType.REFERENCE
        )
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_stores_valid_reaction(self, mock_bot):
        session_data = create_mock_session_data(group_message_id="$event123:example.com")
        mock_bot.database.fetchrow.return_value = session_data
        
        event = create_mock_reaction_event(
            room_id="!grouproom:example.com",
            emoji="🍽️",
            target_event_id="$event123:example.com"
        )
        
        await mock_bot.handle_activity_reaction(event)
        
        # Should store the reaction and send response
        assert mock_bot.database.execute.call_count == 1
        mock_bot.client.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_no_session(self, mock_bot):
        mock_bot.database.fetchrow.return_value = None
        
        event = create_mock_reaction_event(room_id="!grouproom:example.com")
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_no_group_message_id(self, mock_bot):
        session_data = create_mock_session_data(group_message_id=None)
        mock_bot.database.fetchrow.return_value = session_data
        
        event = create_mock_reaction_event(room_id="!grouproom:example.com")
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_wrong_target_event(self, mock_bot):
        session_data = create_mock_session_data(group_message_id="$different:example.com")
        mock_bot.database.fetchrow.return_value = session_data
        
        event = create_mock_reaction_event(
            room_id="!grouproom:example.com",
            target_event_id="$event123:example.com"
        )
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_unknown_emoji(self, mock_bot):
        session_data = create_mock_session_data(group_message_id="$event123:example.com")
        mock_bot.database.fetchrow.return_value = session_data
        
        event = create_mock_reaction_event(
            room_id="!grouproom:example.com",
            emoji="🌮",  # Unknown activity emoji
            target_event_id="$event123:example.com"
        )
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_activity_reaction_send_response_failure(self, mock_bot):
        session_data = create_mock_session_data(group_message_id="$event123:example.com")
        mock_bot.database.fetchrow.return_value = session_data
        mock_bot.client.send_text.side_effect = Exception("Send failed")
        
        event = create_mock_reaction_event(
            room_id="!grouproom:example.com",
            emoji="🍽️",
            target_event_id="$event123:example.com"
        )
        
        await mock_bot.handle_activity_reaction(event)
        
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio 
    async def test_send_group_announcement_fully_available(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        
        await mock_bot.send_group_announcement("test-session", "🏠")
        
        mock_bot.client.send_text.assert_called_once()
        # Should react with all activity emojis
        assert mock_bot.client.react.call_count == len(mock_bot.config.activities)

    @pytest.mark.asyncio
    async def test_send_group_announcement_lunch_only(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        
        await mock_bot.send_group_announcement("test-session", "🏢")
        
        mock_bot.client.send_text.assert_called_once()
        # Should only react with lunch emoji
        assert mock_bot.client.react.call_count == 1

    @pytest.mark.asyncio
    async def test_send_group_announcement_busy_all_day(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        
        await mock_bot.send_group_announcement("test-session", "🕒")
        
        mock_bot.client.send_text.assert_called_once()
        # Should not react with any activity emojis
        mock_bot.client.react.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_group_announcement_send_failure(self, mock_bot):
        mock_bot.client.send_text.side_effect = Exception("Send failed")
        
        await mock_bot.send_group_announcement("test-session", "🏠")
        
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_group_announcement_react_failure(self, mock_bot):
        mock_bot.client.send_text.return_value = EventID("$event123:example.com")
        mock_bot.client.react.side_effect = Exception("React failed")
        
        await mock_bot.send_group_announcement("test-session", "🏠")
        
        mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_reminders_fully_available(self, mock_bot):
        # Mock datetime to ensure reminder times are in future
        with patch('wallingfordbot.bot.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 9, 0)  # 9 AM
            mock_datetime.now.return_value = mock_now
            mock_datetime.replace = datetime.replace
            
            await mock_bot.schedule_reminders("test-session", "🏠")
            
            # Should schedule both lunch and evening reminders
            assert mock_bot.database.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_schedule_reminders_lunch_only(self, mock_bot):
        with patch('wallingfordbot.bot.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 9, 0)  # 9 AM
            mock_datetime.now.return_value = mock_now
            mock_datetime.replace = datetime.replace
            
            await mock_bot.schedule_reminders("test-session", "🏢")
            
            # Should only schedule lunch reminder
            assert mock_bot.database.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_schedule_reminders_busy_all_day(self, mock_bot):
        await mock_bot.schedule_reminders("test-session", "🕒")
        
        # Should not schedule any reminders
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_reminders_past_lunch_time(self, mock_bot):
        # Mock datetime to be after lunch time
        with patch('wallingfordbot.bot.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 14, 0)  # 2 PM - after lunch
            mock_datetime.now.return_value = mock_now
            mock_datetime.replace = datetime.replace
            
            await mock_bot.schedule_reminders("test-session", "🏠")
            
            # Should only schedule evening reminder (lunch time passed)
            assert mock_bot.database.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_schedule_reminders_past_all_times(self, mock_bot):
        # Mock datetime to be after all reminder times
        with patch('wallingfordbot.bot.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 19, 0)  # 7 PM - after all times
            mock_datetime.now.return_value = mock_now
            mock_datetime.replace = datetime.replace
            
            await mock_bot.schedule_reminders("test-session", "🏠")
            
            # Should not schedule any reminders (all times passed)
            mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_pending_reminders_lunch(self, mock_bot):
        reminder_data = create_mock_reminder_data("test-session", "lunch")
        mock_bot.database.fetch.return_value = [reminder_data]
        
        with patch.object(mock_bot, 'send_lunch_reminder') as mock_send:
            await mock_bot.check_pending_reminders()
            
            mock_send.assert_called_once_with("test-session")
            mock_bot.database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_pending_reminders_evening(self, mock_bot):
        reminder_data = create_mock_reminder_data("test-session", "evening")
        mock_bot.database.fetch.return_value = [reminder_data]
        
        with patch.object(mock_bot, 'send_evening_reminder') as mock_send:
            await mock_bot.check_pending_reminders()
            
            mock_send.assert_called_once_with("test-session")

    @pytest.mark.asyncio
    async def test_send_lunch_reminder_with_reactions(self, mock_bot):
        session_data = create_mock_session_data(lunch_reminder_sent=False)
        reaction_data = create_mock_activity_reaction("test-session", activity="lunch")
        
        mock_bot.database.fetchrow.return_value = session_data
        mock_bot.database.fetch.return_value = [reaction_data]
        
        await mock_bot.send_lunch_reminder("test-session")
        
        mock_bot.client.send_text.assert_called_once()
        mock_bot.database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_lunch_reminder_no_reactions(self, mock_bot):
        session_data = create_mock_session_data(lunch_reminder_sent=False)
        mock_bot.database.fetchrow.return_value = session_data
        mock_bot.database.fetch.return_value = []
        
        await mock_bot.send_lunch_reminder("test-session")
        
        mock_bot.client.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_evening_reminder_with_activities(self, mock_bot):
        session_data = create_mock_session_data(evening_reminder_sent=False)
        reaction_data = create_mock_activity_reaction("test-session", activity="pub_dinner")
        
        mock_bot.database.fetchrow.return_value = session_data
        mock_bot.database.fetch.return_value = [reaction_data]
        
        await mock_bot.send_evening_reminder("test-session")
        
        mock_bot.client.send_text.assert_called_once()
        mock_bot.database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_lunch_reminder_already_sent(self, mock_bot):
        session_data = create_mock_session_data(lunch_reminder_sent=True)
        mock_bot.database.fetchrow.return_value = session_data
        
        await mock_bot.send_lunch_reminder("test-session")
        
        mock_bot.client.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_evening_reminder_already_sent(self, mock_bot):
        session_data = create_mock_session_data(evening_reminder_sent=True)
        mock_bot.database.fetchrow.return_value = session_data
        
        await mock_bot.send_evening_reminder("test-session")
        
        mock_bot.client.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_evening_reminder_no_activities(self, mock_bot):
        session_data = create_mock_session_data(evening_reminder_sent=False)
        mock_bot.database.fetchrow.return_value = session_data
        mock_bot.database.fetch.return_value = []  # No evening activities
        
        await mock_bot.send_evening_reminder("test-session")
        
        mock_bot.client.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_pending_reminders_no_reminders(self, mock_bot):
        mock_bot.database.fetch.return_value = []
        
        await mock_bot.check_pending_reminders()
        
        mock_bot.database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_pending_reminders_exception_handling(self, mock_bot):
        reminder_data = create_mock_reminder_data("test-session", "lunch")
        mock_bot.database.fetch.return_value = [reminder_data]
        
        with patch.object(mock_bot, 'send_lunch_reminder', side_effect=Exception("Reminder failed")):
            await mock_bot.check_pending_reminders()
            
            mock_bot.log.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_reminder_loop_cancellation(self, mock_bot):
        with patch('asyncio.sleep', side_effect=asyncio.CancelledError()):
            await mock_bot.reminder_loop()
            
        # Should exit gracefully on cancellation

    @pytest.mark.asyncio
    async def test_reminder_loop_exception_handling(self, mock_bot):
        call_count = 0
        
        async def mock_sleep_then_error(duration):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return  # First call succeeds
            elif call_count == 2:
                raise Exception("Test error")  # Second call fails
            else:
                raise asyncio.CancelledError()  # Third call cancels
        
        with patch('asyncio.sleep', side_effect=mock_sleep_then_error), \
             patch.object(mock_bot, 'check_pending_reminders', side_effect=Exception("Check failed")):
            await mock_bot.reminder_loop()
            
            mock_bot.log.exception.assert_called()

    @pytest.mark.asyncio
    async def test_get_config_class(self):
        assert WallingfordBot.get_config_class() == Config

    def test_get_db_upgrade_table(self):
        from wallingfordbot.db import upgrade_table
        assert WallingfordBot.get_db_upgrade_table() == upgrade_table