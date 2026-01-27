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
