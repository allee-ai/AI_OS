# Workspace Module

Virtual filesystem for AI OS — upload, organize, edit, and search user files in a SQLite-backed database separate from git.

---

## Description

The Workspace module provides a virtual file system stored in SQLite. Files uploaded via the UI, created by the agent, or written through the CLI all live here. The workspace is completely separate from the git repository — it's the agent's working directory.

---

## Architecture

<!-- ARCHITECTURE:workspace -->
### Directory Structure

```
workspace/
├── api.py               # FastAPI endpoints (upload, move, delete, search, etc.)
├── schema.py            # SQLite tables, CRUD, FTS5 indexing
├── cli.py               # Headless CLI (/files commands)
├── summarizer.py        # LLM-powered file summarization
├── __init__.py
├── aios-demo/           # Demo website (community hub)
└── allee-ai.github.io/  # Project documentation site
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `workspace_files` | File metadata, content, parent paths, MIME types |
| `workspace_fts` | FTS5 full-text search index on file content |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workspace/files` | List files (with parent_path filter) |
| POST | `/api/workspace/upload` | Upload a file |
| DELETE | `/api/workspace/files/{id}` | Delete a file |
| POST | `/api/workspace/folders` | Create folder |
| PUT | `/api/workspace/move` | Move/rename files |
| GET | `/api/workspace/files/{id}/content` | Download file content |
| GET | `/api/workspace/files/{id}/meta` | Get file metadata |
| PUT | `/api/workspace/files/{id}/edit` | Edit file content in-place |
| GET | `/api/workspace/search` | FTS5 search within file contents |
| GET | `/api/workspace/recent` | Recently modified files |
| POST | `/api/workspace/pin/{id}` | Pin a file |
| GET | `/api/workspace/pinned` | List pinned files |
| POST | `/api/workspace/notes` | Create a quick note |
| GET | `/api/workspace/notes` | List notes |
| POST | `/api/workspace/summarize/{id}` | Generate LLM summary |

### Agent Tools

The workspace is accessible to the LLM via two registered tools:

| Tool | Actions | Safety |
|------|---------|--------|
| `workspace_read` | `read_file`, `list_directory`, `search_files` | All safe (auto-execute) |
| `workspace_write` | `write_file`, `create_directory`, `move_file`, `delete_file` | `delete_file` blocked by default |

### CLI Commands

```bash
/files [path]           # List directory
/files read <path>      # Show file content
/files write <path> <c> # Create/overwrite file
/files mkdir <path>     # Create directory
/files mv <old> <new>   # Move/rename
/files rm <path>        # Delete file
/files search <query>   # Full-text search
/files stats            # File count and total size
```

### Status

| Feature | Status |
|---------|--------|
| File upload | ✅ |
| Folder organization | ✅ |
| Full-text search (FTS5) | ✅ |
| In-browser editing (CodeMirror) | ✅ |
| Auto-summarization | ✅ |
| Agent read tools | ✅ |
| Agent write/move tools | ✅ |
| LLM file sorting | ✅ |
| Headless CLI | ✅ |
| Version history | 📋 |
<!-- /ARCHITECTURE:workspace -->

---

## Roadmap

<!-- ROADMAP:workspace -->
### Ready for contributors
- [x] **File rendering** — Type-aware rendering for text, code, markdown, images
- [x] **In-browser editing** — CodeMirror 6 editor with syntax highlighting
- [x] **Auto-summarization** — LLM-powered summaries stored in summary column
- [x] **Full-text search** — FTS5 search within file contents
- [x] **Agent tools** — workspace_read + workspace_write with move_file for LLM sorting
- [x] **Headless CLI** — Full read/write/move/delete from terminal
- [ ] **Agent file references** — Agent cites specific workspace files in responses
- [ ] **Version history** — Track file changes over time
<!-- /ROADMAP:workspace -->
- [ ] **Sharing** — Share files with external users

### Starter tasks
- [x] Add file preview (markdown, code)
- [x] Show file metadata (size, modified)
- [ ] File type icons in list view
<!-- /ROADMAP:workspace -->

---

## Changelog

<!-- CHANGELOG:workspace -->
### 2026-01-27
- File upload and folder organization
- FastAPI endpoints for CRUD

### 2026-01-20
- SQLite schema for file metadata
<!-- /CHANGELOG:workspace -->
