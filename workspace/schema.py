"""
Workspace Schema - Virtual Filesystem in SQLite
===============================================
DB-backed file storage with metadata, search, and LLM-ready chunking.

Tables:
- workspace_files: File content and metadata
- workspace_chunks: Pre-chunked content for LLM context
"""

import sqlite3
import json
from contextlib import closing
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import sys
import hashlib
import mimetypes

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data.db import get_connection


# =============================================================================
# Table Initialization
# =============================================================================

def init_workspace_tables():
    """Create workspace tables if they don't exist."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        # Main files table - virtual filesystem
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                is_folder INTEGER DEFAULT 0,
                parent_path TEXT,
                content BLOB,
                mime_type TEXT,
                size INTEGER DEFAULT 0,
                hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                modified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata JSON DEFAULT '{}',
                indexed INTEGER DEFAULT 0,
                FOREIGN KEY (parent_path) REFERENCES workspace_files(path)
            )
        """)
        
        # Pre-chunked content for LLM consumption
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER,
                embedding BLOB,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES workspace_files(id) ON DELETE CASCADE,
                UNIQUE(file_id, chunk_index)
            )
        """)
        
        # Full-text search on chunks
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS workspace_fts USING fts5(
                content,
                content_rowid=id,
                tokenize='porter'
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ws_parent ON workspace_files(parent_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ws_mime ON workspace_files(mime_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ws_indexed ON workspace_files(indexed)")
        
        # Create root folder if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO workspace_files (path, name, is_folder, parent_path)
            VALUES ('/', 'root', 1, NULL)
        """)
        
        conn.commit()
    return True


# =============================================================================
# File Operations
# =============================================================================

def normalize_path(path: str) -> str:
    """Normalize path to consistent format."""
    if not path.startswith('/'):
        path = '/' + path
    # Remove trailing slash except for root
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    # Collapse multiple slashes
    while '//' in path:
        path = path.replace('//', '/')
    return path


def get_parent_path(path: str) -> str:
    """Get parent directory path."""
    path = normalize_path(path)
    if path == '/':
        return None
    parent = '/'.join(path.split('/')[:-1])
    return parent if parent else '/'


def create_file(
    path: str,
    content: bytes,
    mime_type: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create or update a file in the workspace."""
    init_workspace_tables()
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        name = path.split('/')[-1]
        parent_path = get_parent_path(path)
        
        # Auto-detect mime type
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(name)
            mime_type = mime_type or 'application/octet-stream'
        
        # Compute hash
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        
        # Ensure parent folder exists
        if parent_path and parent_path != '/':
            ensure_folder(parent_path)
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO workspace_files 
                (path, name, is_folder, parent_path, content, mime_type, size, hash, modified_at, metadata)
            VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                content = excluded.content,
                mime_type = excluded.mime_type,
                size = excluded.size,
                hash = excluded.hash,
                modified_at = excluded.modified_at,
                metadata = excluded.metadata,
                indexed = 0
        """, (path, name, parent_path, content, mime_type, len(content), file_hash, now, 
              json.dumps(metadata or {})))
        
        conn.commit()
    
    return {
        "path": path,
        "name": name,
        "size": len(content),
        "mime_type": mime_type,
        "hash": file_hash,
        "created": True
    }


def ensure_folder(path: str) -> bool:
    """Create folder and all parent folders."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        if path == '/':
            return True
        
        # Build list of folders to create
        parts = path.split('/')[1:]  # Skip empty first element
        current = ''
        
        for part in parts:
            parent = current if current else '/'
            current = current + '/' + part
            
            cursor.execute("""
                INSERT OR IGNORE INTO workspace_files 
                    (path, name, is_folder, parent_path)
                VALUES (?, ?, 1, ?)
            """, (current, part, parent))
        
        conn.commit()
    return True


def get_file(path: str) -> Optional[Dict[str, Any]]:
    """Get file metadata and content."""
    init_workspace_tables()
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        
        cursor.execute("""
            SELECT id, path, name, is_folder, parent_path, content, mime_type, 
                   size, hash, created_at, modified_at, metadata
            FROM workspace_files WHERE path = ?
        """, (path,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        result = {
            "id": row[0],
            "path": row[1],
            "name": row[2],
            "is_folder": bool(row[3]),
            "parent_path": row[4],
            "content": row[5],
            "mime_type": row[6],
            "size": row[7],
            "hash": row[8],
            "created_at": row[9],
            "modified_at": row[10],
            "metadata": json.loads(row[11]) if row[11] else {}
        }
    return result


def list_directory(path: str = '/') -> List[Dict[str, Any]]:
    """List contents of a directory."""
    init_workspace_tables()
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        
        cursor.execute("""
            SELECT path, name, is_folder, mime_type, size, modified_at
            FROM workspace_files 
            WHERE parent_path = ?
            ORDER BY is_folder DESC, name ASC
        """, (path,))
        
        result = [{
            "path": row[0],
            "name": row[1],
            "is_folder": bool(row[2]),
            "mime_type": row[3],
            "size": row[4],
            "modified_at": row[5]
        } for row in cursor.fetchall()]
    return result


def delete_file(path: str, recursive: bool = False) -> bool:
    """Delete a file or folder."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        if path == '/':
            return False  # Can't delete root
        
        # Check if folder with children
        cursor.execute("SELECT is_folder FROM workspace_files WHERE path = ?", (path,))
        row = cursor.fetchone()
        if not row:
            return False
        
        is_folder = bool(row[0])
        
        if is_folder:
            cursor.execute("SELECT COUNT(*) FROM workspace_files WHERE parent_path = ?", (path,))
            child_count = cursor.fetchone()[0]
            
            if child_count > 0 and not recursive:
                raise ValueError("Folder not empty. Use recursive=True to delete.")
            
            if recursive:
                # Delete all descendants
                cursor.execute("""
                    DELETE FROM workspace_files 
                    WHERE path LIKE ? || '/%' OR path = ?
                """, (path, path))
            else:
                cursor.execute("DELETE FROM workspace_files WHERE path = ?", (path,))
        else:
            cursor.execute("DELETE FROM workspace_files WHERE path = ?", (path,))
        
        conn.commit()
    return True


def move_file(old_path: str, new_path: str) -> bool:
    """Move/rename a file or folder."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        old_path = normalize_path(old_path)
        new_path = normalize_path(new_path)
        
        # Get file info
        cursor.execute("SELECT is_folder FROM workspace_files WHERE path = ?", (old_path,))
        row = cursor.fetchone()
        if not row:
            return False
        
        is_folder = bool(row[0])
        new_name = new_path.split('/')[-1]
        new_parent = get_parent_path(new_path)
        
        # Ensure new parent exists
        if new_parent and new_parent != '/':
            ensure_folder(new_parent)
        
        # Update the file/folder
        cursor.execute("""
            UPDATE workspace_files 
            SET path = ?, name = ?, parent_path = ?, modified_at = ?
            WHERE path = ?
        """, (new_path, new_name, new_parent, datetime.utcnow().isoformat(), old_path))
        
        # If folder, update all children paths
        if is_folder:
            cursor.execute("""
                UPDATE workspace_files 
                SET path = ? || substr(path, ?),
                    parent_path = CASE 
                        WHEN parent_path = ? THEN ?
                        ELSE ? || substr(parent_path, ?)
                    END
                WHERE path LIKE ? || '/%'
            """, (new_path, len(old_path) + 1, old_path, new_path, 
                  new_path, len(old_path) + 1, old_path))
        
        conn.commit()
    return True


# =============================================================================
# Search & Indexing
# =============================================================================

def search_files(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Full-text search across file contents."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        # Search in FTS table
        cursor.execute("""
            SELECT wf.path, wf.name, wf.mime_type, wf.size, 
                   snippet(workspace_fts, 0, '<mark>', '</mark>', '...', 32) as snippet
            FROM workspace_fts fts
            JOIN workspace_chunks wc ON fts.rowid = wc.id
            JOIN workspace_files wf ON wc.file_id = wf.id
            WHERE workspace_fts MATCH ?
            GROUP BY wf.id
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        
        result = [{
            "path": row[0],
            "name": row[1],
            "mime_type": row[2],
            "size": row[3],
            "snippet": row[4]
        } for row in cursor.fetchall()]
    return result


def chunk_file(file_id: int, chunk_size: int = 500) -> int:
    """Chunk a file's content for LLM consumption."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        # Get file content
        cursor.execute("SELECT content, mime_type FROM workspace_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return 0
        
        content = row[0]
        mime_type = row[1] or ''
        
        # Only chunk text files
        if not mime_type.startswith('text/') and mime_type not in ['application/json', 'application/javascript']:
            return 0
        
        try:
            text = content.decode('utf-8')
        except:
            return 0
        
        # Simple chunking by paragraphs/lines
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in text.split('\n'):
            line_size = len(line.split())  # Rough token estimate
            if current_size + line_size > chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Clear old chunks
        cursor.execute("DELETE FROM workspace_chunks WHERE file_id = ?", (file_id,))
        cursor.execute("DELETE FROM workspace_fts WHERE rowid IN (SELECT id FROM workspace_chunks WHERE file_id = ?)", (file_id,))
        
        # Insert new chunks
        for i, chunk in enumerate(chunks):
            cursor.execute("""
                INSERT INTO workspace_chunks (file_id, chunk_index, content, token_count)
                VALUES (?, ?, ?, ?)
            """, (file_id, i, chunk, len(chunk.split())))
            
            chunk_id = cursor.lastrowid
            
            # Add to FTS
            cursor.execute("INSERT INTO workspace_fts (rowid, content) VALUES (?, ?)", 
                          (chunk_id, chunk))
        
        # Mark file as indexed
        cursor.execute("UPDATE workspace_files SET indexed = 1 WHERE id = ?", (file_id,))
        
        conn.commit()
    return len(chunks)


def get_file_chunks(path: str) -> List[str]:
    """Get pre-chunked content for a file (LLM-ready)."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        path = normalize_path(path)
        
        cursor.execute("""
            SELECT wc.content 
            FROM workspace_chunks wc
            JOIN workspace_files wf ON wc.file_id = wf.id
            WHERE wf.path = ?
            ORDER BY wc.chunk_index
        """, (path,))
        
        result = [row[0] for row in cursor.fetchall()]
    return result


def get_workspace_stats() -> Dict[str, Any]:
    """Get workspace statistics."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM workspace_files WHERE is_folder = 0")
        file_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM workspace_files WHERE is_folder = 1")
        folder_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(size) FROM workspace_files")
        total_size = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM workspace_chunks")
        chunk_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM workspace_files WHERE indexed = 1")
        indexed_count = cursor.fetchone()[0]
    
    return {
        "files": file_count,
        "folders": folder_count,
        "total_size_bytes": total_size,
        "chunks": chunk_count,
        "indexed_files": indexed_count
    }


# Initialize on import
init_workspace_tables()
