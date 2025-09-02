import pytest
from unittest.mock import AsyncMock, MagicMock

from mautrix.util.async_db import Connection, Scheme

from wallingfordbot.db import (
    upgrade_table,
    create_workflow_session_table,
    create_activity_reaction_table, 
    create_scheduled_reminder_table
)


class TestDatabaseMigrations:
    
    @pytest.mark.asyncio
    async def test_create_workflow_session_table(self):
        conn = AsyncMock(spec=Connection)
        
        await create_workflow_session_table(conn, Scheme.POSTGRES)
        
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE workflow_session" in sql
        assert "id TEXT PRIMARY KEY" in sql
        assert "date TEXT NOT NULL" in sql
        assert "alex_confirmation TEXT" in sql
        assert "confirmed BOOLEAN DEFAULT FALSE" in sql

    @pytest.mark.asyncio
    async def test_create_activity_reaction_table_postgres(self):
        conn = AsyncMock(spec=Connection)
        
        await create_activity_reaction_table(conn, Scheme.POSTGRES)
        
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE activity_reaction" in sql
        assert "GENERATED ALWAYS AS IDENTITY" in sql
        assert "session_id TEXT NOT NULL" in sql
        assert "user_id TEXT NOT NULL" in sql
        assert "activity TEXT NOT NULL" in sql
        assert "emoji TEXT NOT NULL" in sql

    @pytest.mark.asyncio
    async def test_create_activity_reaction_table_sqlite(self):
        conn = AsyncMock(spec=Connection)
        
        await create_activity_reaction_table(conn, Scheme.SQLITE)
        
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE activity_reaction" in sql
        assert "AUTOINCREMENT" in sql
        assert "session_id TEXT NOT NULL" in sql

    @pytest.mark.asyncio
    async def test_create_scheduled_reminder_table_postgres(self):
        conn = AsyncMock(spec=Connection)
        
        await create_scheduled_reminder_table(conn, Scheme.POSTGRES)
        
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE scheduled_reminder" in sql
        assert "GENERATED ALWAYS AS IDENTITY" in sql
        assert "reminder_type TEXT NOT NULL" in sql
        assert "scheduled_time TIMESTAMP NOT NULL" in sql
        assert "sent BOOLEAN DEFAULT FALSE" in sql

    @pytest.mark.asyncio
    async def test_create_scheduled_reminder_table_sqlite(self):
        conn = AsyncMock(spec=Connection)
        
        await create_scheduled_reminder_table(conn, Scheme.SQLITE)
        
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "CREATE TABLE scheduled_reminder" in sql
        assert "AUTOINCREMENT" in sql

    def test_upgrade_table_registration(self):
        """Test that all migrations are properly registered."""
        assert len(upgrade_table.upgrades) == 3