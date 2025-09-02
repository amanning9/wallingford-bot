import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Type, Optional

from aiohttp.web import Request, Response
from maubot import Plugin, MessageEvent
from maubot.handlers import web
from maubot.handlers.event import on
from mautrix.types import EventType, ReactionEvent, UserID, RoomID, EventID, RelationType
from mautrix.util.logging import TraceLogger

from .config import Config
from .db import upgrade_table


class WallingfordBot(Plugin):
    config: Config
    reminder_task: Optional[asyncio.Task]
    
    async def start(self) -> None:
        self.config.load_and_update()
        self.reminder_task = asyncio.create_task(self.reminder_loop())
        self.log.info("WallingfordBot started")
    
    async def stop(self) -> None:
        if self.reminder_task:
            self.reminder_task.cancel()
        self.log.info("WallingfordBot stopped")
    
    @classmethod
    def get_config_class(cls) -> Type[Config]:
        return Config
    
    @classmethod
    def get_db_upgrade_table(cls):
        return upgrade_table
    
    @web.post("/webhook/homeassistant")
    async def homeassistant_webhook(self, request: Request) -> Response:
        try:
            # Verify webhook secret
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return Response(status=401, text="Unauthorized")
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            if token != self.config.webhook_secret:
                return Response(status=401, text="Invalid token")
            
            # Parse request
            data = await request.json()
            self.log.info(f"Received Home Assistant webhook: {data}")
            
            # Check if this is a test request
            is_test = data.get('test', False)
            
            # Start workflow
            await self.start_office_workflow(is_test=is_test)
            
            return Response(status=200, text="OK")
            
        except Exception as e:
            self.log.exception("Error handling Home Assistant webhook")
            return Response(status=500, text="Internal Server Error")
    
    async def start_office_workflow(self, is_test: bool = False) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        session_id = f"office-{today}-{uuid.uuid4().hex[:8]}"
        
        self.log.info(f"DEBUG: Starting office workflow for date {today}, test mode: {is_test}")
        
        # If this is a test, clear any existing sessions for today
        if is_test:
            self.log.info(f"DEBUG: Test mode - clearing existing sessions for {today}")
            await self.database.execute(
                "DELETE FROM activity_reaction WHERE session_id IN (SELECT id FROM workflow_session WHERE date = $1)",
                today
            )
            await self.database.execute(
                "DELETE FROM scheduled_reminder WHERE session_id IN (SELECT id FROM workflow_session WHERE date = $1)",
                today
            )
            await self.database.execute(
                "DELETE FROM workflow_session WHERE date = $1",
                today
            )
        
        # Check if we already have a session for today
        existing_session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE date = $1", today
        )
        
        if existing_session:
            self.log.info(f"DEBUG: Found existing session: {existing_session}")
            if existing_session['confirmed']:
                self.log.info(f"Workflow already completed today: {existing_session['id']}")
                return
            else:
                self.log.info(f"DEBUG: Session exists but not confirmed, proceeding with new request")
        else:
            self.log.info(f"DEBUG: No existing session found for {today}")
        
        # Create new workflow session
        await self.database.execute(
            "INSERT INTO workflow_session (id, date) VALUES ($1, $2)",
            session_id, today
        )
        self.log.info(f"Started new office workflow: {session_id}")
        
        # Send confirmation request to Alex
        await self.send_confirmation_request(session_id)
    
    async def send_confirmation_request(self, session_id: str) -> None:
        message = self.config.messages["confirmation_request"]
        
        try:
            event = await self.client.send_text(
                room_id=RoomID(self.config.alex_private_room),
                text=message
            )
            
            # React with available options to show Alex what to choose from
            for emoji in self.config.confirmation_emojis:
                await self.client.react(
                    room_id=RoomID(self.config.alex_private_room), 
                    event_id=event,
                    key=emoji
                )
            
            # Add thumbs up for confirmation
            await self.client.react(
                room_id=RoomID(self.config.alex_private_room),
                event_id=event,
                key="👍"
            )
            
            self.log.info(f"Sent confirmation request for session {session_id}")
            
        except Exception as e:
            self.log.exception(f"Failed to send confirmation request: {e}")
    
    @on(EventType.REACTION)
    async def handle_reaction_event(self, event: ReactionEvent) -> None:
        await self.handle_reaction(event)
    
    async def handle_reaction(self, event: ReactionEvent) -> None:
        self.log.info(f"DEBUG: Handle reaction called - sender: {event.sender}, alex_user_id: {self.config.alex_user_id}")
        
        # Only handle annotation reactions (not other relation types)
        if event.content.relates_to.rel_type != RelationType.ANNOTATION:
            self.log.info(f"DEBUG: Skipping non-annotation reaction: {event.content.relates_to.rel_type}")
            return
            
        # Check if this is in Alex's private room (confirmation reactions)
        if str(event.room_id) == self.config.alex_private_room and event.sender == UserID(self.config.alex_user_id):
            self.log.info(f"DEBUG: Handling Alex's confirmation reaction")
            await self.handle_confirmation_reaction(event)
        else:
            # All other reactions (including Alex's activity reactions) go to activity handler
            self.log.info(f"DEBUG: Reaction not Alex confirmation, checking if it's activity reaction")
            await self.handle_activity_reaction(event)
    
    async def handle_confirmation_reaction(self, event: ReactionEvent) -> None:
        emoji = event.content.relates_to.key
        self.log.info(f"DEBUG: Handling confirmation reaction {emoji}")
        
        # Check if this is a confirmation emoji
        if emoji not in self.config.confirmation_emojis:
            self.log.info(f"DEBUG: {emoji} not in confirmation emojis {self.config.confirmation_emojis}")
            if emoji == "👍":
                self.log.info(f"DEBUG: Detected thumbs up ({emoji}), calling confirm_previous_reaction")
                # This might be confirming a previous choice
                await self.confirm_previous_reaction(event)
            return
        
        # Store the emoji choice (not yet confirmed)
        today = datetime.now().strftime("%Y-%m-%d")
        self.log.info(f"DEBUG: Looking for session on date {today}")
        session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE date = $1", today
        )
        if session:
            self.log.info(f"DEBUG: Found session {session['id']}, updating with choice {emoji}")
            await self.database.execute(
                "UPDATE workflow_session SET alex_confirmation = $1, confirmed = $2 WHERE id = $3",
                emoji, False, session['id']
            )
            self.log.info(f"Alex chose {emoji} for session {session['id']}")
        else:
            self.log.warning(f"DEBUG: No session found for date {today}")
    
    async def confirm_previous_reaction(self, event: ReactionEvent) -> None:
        today = datetime.now().strftime("%Y-%m-%d") 
        self.log.info(f"DEBUG: Confirming previous reaction for date {today}")
        session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE date = $1", today
        )
        
        if not session:
            self.log.warning(f"DEBUG: No session found for confirmation on {today}")
            return
            
        if not session['alex_confirmation']:
            self.log.warning(f"DEBUG: Session {session['id']} has no alex_confirmation set")
            return
        
        self.log.info(f"DEBUG: Found session {session['id']} with alex_confirmation={session['alex_confirmation']}")
        
        # Confirm the choice and proceed
        await self.database.execute(
            "UPDATE workflow_session SET alex_confirmation = $1, confirmed = $2 WHERE id = $3",
            session['alex_confirmation'], True, session['id']
        )
        self.log.info(f"Alex confirmed {session['alex_confirmation']} for session {session['id']}")
        
        # Proceed if Alex is staying in Wallingford (🏠, 🏢, or 🕒)
        if session['alex_confirmation'] in ["🏠", "🏢", "🕒"]:
            self.log.info(f"DEBUG: Alex staying in Wallingford ({session['alex_confirmation']}), checking what to announce")
            
            # Always send group announcement when Alex is staying
            await self.send_group_announcement(session['id'], session['alex_confirmation'])
                
            await self.schedule_reminders(session['id'], session['alex_confirmation'])
        else:
            self.log.info(f"DEBUG: Alex not staying in Wallingford ({session['alex_confirmation']}), not sending group announcement")
    
    async def send_group_announcement(self, session_id: str, alex_confirmation: str) -> None:
        # Build activity options text based on Alex's availability
        activity_options = []
        
        # Always include lunch
        lunch_config = self.config.activities["lunch"]
        activity_options.append(f"{lunch_config['emoji']} if you'd like {lunch_config['text']}")
        
        # Only include evening activities if Alex is fully available (🏠)
        if alex_confirmation == "🏠":
            for activity_key, activity_config in self.config.activities.items():
                if activity_key != "lunch":  # Skip lunch as we already added it
                    emoji = activity_config["emoji"]
                    text = activity_config["text"]
                    activity_options.append(f"{emoji} if you'd like {text}")
        
        options_text = ", ".join(activity_options)
        
        # Customize message based on Alex's availability
        if alex_confirmation == "🏠":
            base_message = "Alex is here and free for activities!"
            message = f"{base_message} React with {options_text}"
        elif alex_confirmation == "🏢": 
            base_message = "Alex is here but busy this evening, lunch only!"
            message = f"{base_message} React with {options_text}"
        else:  # 🕒 - busy all day
            message = "Alex is here but busy all day. No activities today, but he's staying the night!"
        
        try:
            event = await self.client.send_text(
                room_id=RoomID(self.config.group_chat_room),
                text=message
            )
            
            # Store group message ID
            await self.database.execute(
                "UPDATE workflow_session SET group_message_id = $1 WHERE id = $2",
                str(event), session_id
            )
            
            # React with activity emojis based on Alex's availability
            if alex_confirmation in ["🏠", "🏢"]:  # Only add emojis if there are activities
                # Always add lunch emoji for 🏠 and 🏢
                await self.client.react(
                    room_id=RoomID(self.config.group_chat_room),
                    event_id=event,
                    key=self.config.activities["lunch"]["emoji"]
                )
                
                # Only add evening activity emojis if Alex is fully available (🏠)
                if alex_confirmation == "🏠":
                    for activity_key, activity_config in self.config.activities.items():
                        if activity_key != "lunch":  # Skip lunch as we already added it
                            await self.client.react(
                                room_id=RoomID(self.config.group_chat_room),
                                event_id=event,
                                key=activity_config["emoji"]
                            )
            # For 🕒 (busy all day), no activity emojis are added
            
            self.log.info(f"Sent group announcement for session {session_id}")
            
        except Exception as e:
            self.log.exception(f"Failed to send group announcement: {e}")
    
    async def handle_activity_reaction(self, event: ReactionEvent) -> None:
        self.log.info(f"DEBUG: Activity reaction handler called - room: {event.room_id}, sender: {event.sender}, emoji: {event.content.relates_to.key}")
        
        # Don't respond to the bot's own reactions
        if str(event.sender) == str(self.client.mxid):
            self.log.info(f"DEBUG: Ignoring bot's own reaction from {event.sender}")
            return
        
        # Check if this is a reaction to a group message
        if str(event.room_id) != self.config.group_chat_room:
            self.log.info(f"DEBUG: Room {event.room_id} != group chat room {self.config.group_chat_room}")
            return
        
        # Only handle annotation reactions 
        if event.content.relates_to.rel_type != RelationType.ANNOTATION:
            self.log.info(f"DEBUG: Relation type {event.content.relates_to.rel_type} != ANNOTATION")
            return
            
        today = datetime.now().strftime("%Y-%m-%d")
        session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE date = $1", today
        )
        if not session:
            self.log.info(f"DEBUG: No session found for date {today}")
            return
        if not session['group_message_id']:
            self.log.info(f"DEBUG: Session {session['id']} has no group_message_id")
            return
        
        self.log.info(f"DEBUG: Checking if reaction event {event.content.relates_to.event_id} == session group_message_id {session['group_message_id']}")
        
        # Check if reaction is to our group message
        if str(event.content.relates_to.event_id) != session['group_message_id']:
            self.log.info(f"DEBUG: Event ID mismatch: {event.content.relates_to.event_id} != {session['group_message_id']}")
            return
        
        emoji = event.content.relates_to.key
        self.log.info(f"DEBUG: Processing activity emoji: {emoji}")
        
        # Find which activity this emoji corresponds to
        activity_key = None
        for key, config in self.config.activities.items():
            self.log.info(f"DEBUG: Checking activity {key} with emoji {config['emoji']} against {emoji}")
            if config["emoji"] == emoji:
                activity_key = key
                break
        
        if not activity_key:
            self.log.info(f"DEBUG: No activity found for emoji {emoji}")
            return
        
        self.log.info(f"DEBUG: Found activity {activity_key} for emoji {emoji}, storing reaction")
        
        # Store the reaction
        await self.database.execute(
            "INSERT INTO activity_reaction (session_id, user_id, activity, emoji) VALUES ($1, $2, $3, $4)",
            session['id'], str(event.sender), activity_key, emoji
        )
        
        self.log.info(f"User {event.sender} reacted with {emoji} for {activity_key}")
        
        # Send automatic response for the activity
        activity_config = self.config.activities[activity_key]
        if 'response' in activity_config:
            response_message = activity_config['response']
            try:
                await self.client.send_text(
                    room_id=RoomID(self.config.group_chat_room),
                    text=response_message
                )
                self.log.info(f"Sent activity response: {response_message}")
            except Exception as e:
                self.log.exception(f"Failed to send activity response: {e}")
    
    async def schedule_reminders(self, session_id: str, alex_confirmation: str) -> None:
        now = datetime.now()
        timing = self.config.timing
        
        # Only schedule lunch reminders if Alex is available for lunch (🏠 or 🏢)
        if alex_confirmation in ["🏠", "🏢"]:
            # Parse lunch time
            lunch_time_str = timing["lunch_time"]  # "12:30"
            lunch_hour, lunch_minute = map(int, lunch_time_str.split(":"))
            lunch_time = now.replace(hour=lunch_hour, minute=lunch_minute, second=0, microsecond=0)
            
            # Schedule lunch reminder
            lunch_reminder_time = lunch_time - timedelta(minutes=timing["lunch_reminder_offset"])
            if lunch_reminder_time > now:
                await self.database.execute(
                    "INSERT INTO scheduled_reminder (session_id, reminder_type, scheduled_time) VALUES ($1, $2, $3)",
                    session_id, "lunch", lunch_reminder_time
                )
        
        # Only schedule evening reminders if Alex is fully available (🏠)
        if alex_confirmation == "🏠":
            # Parse work end time  
            work_end_str = timing["work_end_time"]  # "17:30"
            work_hour, work_minute = map(int, work_end_str.split(":"))
            work_end_time = now.replace(hour=work_hour, minute=work_minute, second=0, microsecond=0)
            
            # Schedule evening reminder
            evening_reminder_time = work_end_time - timedelta(minutes=timing["evening_reminder_offset"])
            if evening_reminder_time > now:
                await self.database.execute(
                    "INSERT INTO scheduled_reminder (session_id, reminder_type, scheduled_time) VALUES ($1, $2, $3)",
                    session_id, "evening", evening_reminder_time
                )
        
        self.log.info(f"Scheduled reminders for session {session_id} with availability {alex_confirmation}")
    
    async def reminder_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.check_pending_reminders()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.exception("Error in reminder loop")
    
    async def check_pending_reminders(self) -> None:
        now = datetime.now()
        pending_reminders = await self.database.fetch(
            "SELECT * FROM scheduled_reminder WHERE scheduled_time <= $1 AND sent = FALSE",
            now
        )
        
        for reminder in pending_reminders:
            try:
                if reminder['reminder_type'] == "lunch":
                    await self.send_lunch_reminder(reminder['session_id'])
                elif reminder['reminder_type'] == "evening":
                    await self.send_evening_reminder(reminder['session_id'])
                
                await self.database.execute(
                    "UPDATE scheduled_reminder SET sent = TRUE WHERE id = $1",
                    reminder['id']
                )
                
            except Exception as e:
                self.log.exception(f"Failed to send {reminder['reminder_type']} reminder")
    
    async def send_lunch_reminder(self, session_id: str) -> None:
        session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE id = $1", session_id
        )
        if not session or session['lunch_reminder_sent']:
            return
        
        # Check if anyone wants lunch
        reactions = await self.database.fetch(
            "SELECT * FROM activity_reaction WHERE session_id = $1", session_id
        )
        lunch_people = [r for r in reactions if r['activity'] == "lunch"]
        
        if not lunch_people:
            return
        
        message = self.config.messages["lunch_reminder"].format(
            lunch_time=self.config.timing["lunch_time"]
        )
        
        await self.client.send_text(
            room_id=RoomID(self.config.alex_private_room),
            text=message
        )
        
        await self.database.execute(
            "UPDATE workflow_session SET lunch_reminder_sent = TRUE WHERE id = $1",
            session_id
        )
        self.log.info(f"Sent lunch reminder for session {session_id}")
    
    async def send_evening_reminder(self, session_id: str) -> None:
        session = await self.database.fetchrow(
            "SELECT * FROM workflow_session WHERE id = $1", session_id
        )
        if not session or session['evening_reminder_sent']:
            return
        
        # Get evening activities that people want
        reactions = await self.database.fetch(
            "SELECT * FROM activity_reaction WHERE session_id = $1", session_id
        )
        evening_activities = []
        
        for reaction in reactions:
            if reaction['activity'] in ["picnic_dinner", "pub_dinner", "evening_walk", "evening_cycle", "other_fun"]:
                activity_text = self.config.activities[reaction['activity']]["text"]
                evening_activities.append(activity_text)
        
        if not evening_activities:
            return
        
        plans_text = ", ".join(set(evening_activities))  # Remove duplicates
        message = self.config.messages["evening_reminder"].format(
            evening_plans=plans_text
        )
        
        await self.client.send_text(
            room_id=RoomID(self.config.alex_private_room),
            text=message
        )
        
        await self.database.execute(
            "UPDATE workflow_session SET evening_reminder_sent = TRUE WHERE id = $1",
            session_id
        )
        self.log.info(f"Sent evening reminder for session {session_id}")