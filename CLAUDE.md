# Wallingford Bot - Maubot Plugin

## Project Overview
Complete maubot plugin that coordinates social activities when Alex arrives at the office. Named after Wallingford, UK.

## Key Technical Details

### Final Working Structure
- **Version**: 1.0.16 (working version)
- **Database**: Uses asyncpg with proper maubot database interface
- **Event Handling**: Uses `@on(EventType.REACTION)` decorator with `RelationType.ANNOTATION`

### Critical Technical Solutions Discovered

1. **Database Interface**:
   - DO NOT use wrapper classes around `self.database`
   - Use `self.database.execute()`, `self.database.fetchrow()`, `self.database.fetch()` directly
   - Follow pattern from official StorageBot example
   - Must have `database_type: asyncpg` in maubot.yaml

2. **Reaction Event Handling**:
   - Use `@on(EventType.REACTION)` decorator (NOT `on_event` method)
   - Import: `from maubot.handlers.event import on`
   - Check `event.content.relates_to.rel_type == RelationType.ANNOTATION`
   - Access emoji via `event.content.relates_to.key`
   - Access target event via `event.content.relates_to.event_id`

3. **Configuration**:
   - Matrix user IDs MUST have colon: `@alex:example.com` (not `@alexexample.com`)
   - Room IDs format: `!roomid:server.domain`
   - Config updates require manual updating in maubot web interface (not auto-updated on plugin upload)

4. **Activity Reaction Filtering**:
   - MUST filter out bot's own reactions: `if str(event.sender) == str(self.client.mxid): return`
   - Bot adds placeholder emojis which trigger its own event handlers

## Workflow Process
1. Home Assistant webhook triggers office arrival
2. Bot sends confirmation message to Alex's private room with preloaded reactions
3. Alex reacts with availability + 👍 (confirm):
   - 🏠 = Free for all activities (lunch + evening)
   - 🏢 = Busy evening, lunch only
   - 🕒 = Busy all day (announcement only)
   - 🚗 = Going home (no announcement)
   - ❓ = Unsure (no announcement)
4. Bot sends customized group announcement based on Alex's availability
5. Others react with activity preferences, bot responds automatically:
   - 🍽️ → "Great! Alex will join for lunch at 12:30."
   - 🥪 → "Alex will go shopping on his way home for a picnic dinner!"
   - 🍺 → "Sounds good! Alex will meet you at the pub for dinner."
   - etc.
6. Bot schedules and sends appropriate reminders based on availability

## Database Schema
- `workflow_session` - Daily workflow tracking
- `activity_reaction` - User activity preferences
- `scheduled_reminder` - Timed reminders

## File Structure
```
wallingford-bot/
├── spec.md              # Original requirements
├── maubot.yaml          # Plugin metadata
├── base-config.yaml     # Configuration template
└── wallingfordbot/
    ├── __init__.py      # Module init
    ├── bot.py           # Main plugin logic
    ├── config.py        # Configuration management
    └── db.py            # Database migrations only
```

## Build & Deploy Commands
```bash
cd wallingford-bot
uv run mbc build --upload  # Auto-updates running instance
```

## Testing
1. Trigger webhook with test mode (clears existing sessions) using command from CLAUDE.secrets.md file in root of repository.
2. React with availability emoji (🏠/🏢/🕒/🚗/❓) then 👍 in private room
3. Check for customized group announcement based on availability
4. Test activity reactions and automatic responses

## Known Issues Fixed
- ❌ Database wrapper classes cause `AttributeError: 'Engine' object has no attribute 'fetchrow'`
- ❌ `on_event` method doesn't receive events (use `@on` decorator)
- ❌ `EventType.ROOM_REACTION` doesn't exist (use `EventType.REACTION`)
- ❌ Incorrect user ID format breaks reaction detection
- ❌ Bot responding to its own reactions when adding placeholder emojis
- ❌ Sessions persisting across test runs (solved with test mode webhook parameter)

## Important References
- Maubot database example: https://github.com/maubot/maubot/tree/master/examples/database
- Reaction events: https://docs.mau.fi/python/latest/api/mautrix.types.html#mautrix.types.ReactionEvent
- Maubot docs: https://docs.mau.fi/maubot/dev/

## Security & Secrets Management
- **CRITICAL**: No secrets should be put in any file which is not in the .gitignore file
- All actual secrets useful to claude must be stored in CLAUDE.secrets.md (gitignored)
- Configuration files (base-config.yaml) contain only placeholder values for public repository
- Repository has been audited and is safe for public commit

## Status
✅ Webhook working with test mode
✅ Database operations working
✅ Reaction handling implemented with proper filtering
✅ Multiple availability options (🏠/🏢/🕒/🚗/❓)
✅ Automatic activity responses
✅ Customized group announcements
✅ Full workflow tested and working (v1.0.16)
