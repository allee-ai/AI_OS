"""
Tests for Database layer.

Tests:
- Connection management (get_connection)
- Demo/Personal mode switching
- WAL mode and concurrency
"""

import pytest
from pathlib import Path
import sys
import sqlite3
import threading

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDatabaseConnection:
    """Test database connection management."""
    
    def test_get_connection_returns_connection(self):
        """get_connection() should return sqlite3.Connection."""
        from data.db import get_connection
        
        conn = get_connection()
        
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
    
    def test_connection_has_row_factory(self):
        """Connection should have Row factory for dict-like access."""
        from data.db import get_connection
        
        conn = get_connection()
        
        assert conn.row_factory == sqlite3.Row
        conn.close()
    
    def test_connection_wal_mode(self):
        """Connection should use WAL journal mode."""
        from data.db import get_connection
        
        conn = get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        
        assert result[0].lower() == "wal"
        conn.close()
    
    def test_readonly_connection(self):
        """Readonly connection should work."""
        from data.db import get_connection, get_db_path
        
        # Ensure DB exists first
        conn = get_connection()
        conn.close()
        
        # Now test readonly
        conn = get_connection(readonly=True)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


class TestDemoMode:
    """Test demo/personal mode switching."""
    
    def test_is_demo_mode_returns_bool(self):
        """is_demo_mode() should return boolean."""
        from data.db import is_demo_mode
        
        result = is_demo_mode()
        
        assert isinstance(result, bool)
    
    def test_get_db_path_returns_path(self):
        """get_db_path() should return Path object."""
        from data.db import get_db_path
        
        path = get_db_path()
        
        assert isinstance(path, Path)
        assert path.suffix == ".db"


class TestConcurrency:
    """Test database concurrency handling."""
    
    def test_concurrent_reads(self):
        """Multiple threads should read safely."""
        from data.db import get_connection
        
        errors = []
        
        def read_db():
            try:
                conn = get_connection(readonly=True)
                conn.execute("SELECT 1").fetchone()
                conn.close()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=read_db) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrency errors: {errors}"
    
    def test_connection_with_closing_context(self):
        """Connection should work with contextlib.closing() pattern."""
        from contextlib import closing
        from data.db import get_connection
        
        # This is the pattern we use throughout the codebase
        with closing(get_connection()) as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
        
        # Connection should be closed after context
        # (attempting to use it would raise error)
    
    def test_concurrent_writes_with_closing(self):
        """Multiple threads writing with closing() should not deadlock."""
        from contextlib import closing
        from data.db import get_connection
        
        errors = []
        
        def write_db(i):
            try:
                with closing(get_connection()) as conn:
                    # Use a test table that doesn't affect real data
                    conn.execute("CREATE TABLE IF NOT EXISTS _test_concurrent (id INTEGER)")
                    conn.execute("INSERT INTO _test_concurrent VALUES (?)", (i,))
                    conn.commit()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=write_db, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Cleanup
        with closing(get_connection()) as conn:
            conn.execute("DROP TABLE IF EXISTS _test_concurrent")
            conn.commit()
        
        assert len(errors) == 0, f"Concurrent write errors: {errors}"


class TestConversationSource:
    """Test source column for imported conversation tracking."""

    def setup_method(self):
        """Initialize tables before each test."""
        from chat.schema import init_convos_tables
        init_convos_tables()

    def test_source_column_exists(self):
        """convos table should have a source column."""
        from data.db import get_connection
        from contextlib import closing

        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(convos)")
            columns = [col[1] for col in cur.fetchall()]
            assert "source" in columns

    def test_save_conversation_default_source(self):
        """save_conversation without source should default to 'aios'."""
        from chat.schema import save_conversation, get_conversation, delete_conversation

        sid = "test_default_source"
        save_conversation(session_id=sid, name="Default Source Test")
        convo = get_conversation(sid)

        assert convo is not None
        assert convo["source"] == "aios"

        delete_conversation(sid)

    def test_save_conversation_with_source(self):
        """save_conversation with source should persist it."""
        from chat.schema import save_conversation, get_conversation, delete_conversation

        sid = "test_chatgpt_source"
        save_conversation(session_id=sid, name="ChatGPT Import", channel="import", source="chatgpt")
        convo = get_conversation(sid)

        assert convo is not None
        assert convo["source"] == "chatgpt"

        delete_conversation(sid)

    def test_list_conversations_includes_source(self):
        """list_conversations should return source field."""
        from chat.schema import save_conversation, list_conversations, delete_conversation

        sid1 = "test_list_src_native"
        sid2 = "test_list_src_claude"
        save_conversation(session_id=sid1, name="Native Chat")
        save_conversation(session_id=sid2, name="Claude Import", channel="import", source="claude")

        convos = list_conversations(limit=100)
        sources_by_id = {c["session_id"]: c["source"] for c in convos}

        assert sources_by_id.get(sid1) == "aios"
        assert sources_by_id.get(sid2) == "claude"

        delete_conversation(sid1)
        delete_conversation(sid2)

    def test_search_conversations_includes_source(self):
        """search_conversations should return source field."""
        from chat.schema import save_conversation, search_conversations, add_turn, delete_conversation

        sid = "test_search_src"
        save_conversation(session_id=sid, name="Gemini searchable", channel="import", source="gemini")
        add_turn(session_id=sid, user_message="hello gemini", assistant_message="hi there")

        results = search_conversations("gemini", limit=10)
        match = next((r for r in results if r["session_id"] == sid), None)

        assert match is not None
        assert match["source"] == "gemini"

        delete_conversation(sid)

    def test_delete_conversations_by_source(self):
        """delete_conversations_by_source should remove all convos for a source."""
        from chat.schema import (
            save_conversation, add_turn, list_conversations,
            delete_conversations_by_source
        )

        # Create 3 chatgpt imports and 1 native
        for i in range(3):
            sid = f"test_del_src_gpt_{i}"
            save_conversation(session_id=sid, name=f"GPT {i}", channel="import", source="chatgpt")
            add_turn(session_id=sid, user_message="hi", assistant_message="hello")

        save_conversation(session_id="test_del_src_native", name="Native")

        # Delete all chatgpt
        deleted = delete_conversations_by_source("chatgpt")
        assert deleted == 3

        # Native should still exist
        convos = list_conversations(limit=100)
        remaining_ids = [c["session_id"] for c in convos]
        assert "test_del_src_native" in remaining_ids
        for i in range(3):
            assert f"test_del_src_gpt_{i}" not in remaining_ids

        # Cleanup
        from chat.schema import delete_conversation
        delete_conversation("test_del_src_native")
