# Workspace Module

File management for AI OS — upload, organize, and reference user documents.

---

## Description

The Workspace module manages user files within AI OS. It provides file upload, organization, and retrieval so the agent can reference user documents during conversations.

---

## Architecture

<!-- ARCHITECTURE:workspace -->
### Directory Structure

```
workspace/
├── api.py               # FastAPI endpoints
└── schema.py            # SQLite tables for metadata
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workspace/files` | List all files |
| POST | `/api/workspace/upload` | Upload a file |
| DELETE | `/api/workspace/files/{id}` | Delete a file |
| POST | `/api/workspace/folders` | Create folder |
| PUT | `/api/workspace/move` | Move/rename files |

### Status

| Feature | Status |
|---------|--------|
| File upload | ✅ |
| Folder organization | ✅ |
| Full-text search | ✅ |
| Agent reference integration | 📡 |
<!-- /ARCHITECTURE:workspace -->

---

## Roadmap

<!-- ROADMAP:workspace -->
### Ready for contributors
- [x] **File rendering** — Type-aware rendering for text, code, markdown, images
- [ ] **In-browser editing** — Edit files directly in workspace UI with syntax highlighting
- [x] **Auto-summarization** — LLM-powered summaries stored in summary column
- [x] **Full-text search** — FTS5 search within file contents
- [ ] **Agent reference** — Agent cites specific files in responses
- [ ] **Version history** — Track file changes over time
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
