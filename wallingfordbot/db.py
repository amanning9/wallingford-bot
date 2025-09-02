from datetime import datetime
from mautrix.util.async_db import UpgradeTable, Connection, Scheme

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Create workflow session table")
async def create_workflow_session_table(conn: Connection, scheme: Scheme) -> None:
    await conn.execute("""
        CREATE TABLE workflow_session (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            alex_confirmation TEXT,
            confirmed BOOLEAN DEFAULT FALSE,
            group_message_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lunch_reminder_sent BOOLEAN DEFAULT FALSE,
            evening_reminder_sent BOOLEAN DEFAULT FALSE
        )
    """)


@upgrade_table.register(description="Create activity reaction table")
async def create_activity_reaction_table(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.SQLITE:
        await conn.execute("""
            CREATE TABLE activity_reaction (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                activity TEXT NOT NULL,
                emoji TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        await conn.execute("""
            CREATE TABLE activity_reaction (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                activity TEXT NOT NULL,
                emoji TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


@upgrade_table.register(description="Create scheduled reminder table")
async def create_scheduled_reminder_table(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.SQLITE:
        await conn.execute("""
            CREATE TABLE scheduled_reminder (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        await conn.execute("""
            CREATE TABLE scheduled_reminder (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                session_id TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)