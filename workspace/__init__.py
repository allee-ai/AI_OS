"""
Workspace Module - Virtual Filesystem
=====================================
DB-backed file storage with search and LLM-ready chunking.

This is a real OS-level filesystem that:
- Stores files in SQLite (portable, searchable)
- Pre-chunks content for LLM context
- Full-text search across all files
- Metadata and tagging support

Exports:
- router: FastAPI router for all workspace endpoints
- Schema functions for direct DB access
"""

from .api import router
from .schema import (
    # File operations
    create_file,
    get_file,
    list_directory,
    delete_file,
    move_file,
    ensure_folder,
    normalize_path,
    
    # Search & indexing
    search_files,
    chunk_file,
    get_file_chunks,
    
    # Summary & metadata
    update_file_summary,
    get_file_summary,
    get_all_files_metadata,
    search_file_content,
    
    # Stats
    get_workspace_stats,
    init_workspace_tables,
)

from .summarizer import (
    summarize_file,
    summarize_text,
    get_summary_prompt,
    set_summary_prompt,
)

__all__ = [
    "router",
    "create_file",
    "get_file",
    "list_directory",
    "delete_file",
    "move_file",
    "ensure_folder",
    "normalize_path",
    "search_files",
    "chunk_file",
    "get_file_chunks",
    "update_file_summary",
    "get_file_summary",
    "get_all_files_metadata",
    "search_file_content",
    "get_workspace_stats",
    "init_workspace_tables",
    "summarize_file",
    "summarize_text",
    "get_summary_prompt",
    "set_summary_prompt",
]
