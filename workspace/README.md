# Workspace Module

The **Workspace** module manages user files within AI OS. It provides file upload, organization, and retrieval so the agent can reference user documents during conversations.

## Architecture

```
workspace/
├── __init__.py          # Module exports
├── api.py               # FastAPI endpoints
└── schema.py            # SQLite tables for file metadata
```

## API Endpoints

- `GET /api/workspace/files` - List all files
- `POST /api/workspace/upload` - Upload a file
- `DELETE /api/workspace/files/{id}` - Delete a file
- `POST /api/workspace/folders` - Create folder
- `PUT /api/workspace/move` - Move/rename files

## Status

- [x] File upload and storage
- [x] Folder organization
- [ ] Full-text search within files
- [ ] Agent file reference integration

---

## Frontend Module

Located at `frontend/src/modules/workspace/`:

```
workspace/
├── index.ts                    # Module exports
├── pages/
│   └── WorkspacePage.tsx       # Main workspace view
├── components/
│   ├── WorkspacePanel.tsx      # File browser panel
│   ├── WorkspacePanel.css
│   ├── WorkspaceLayout.tsx     # Layout wrapper
│   ├── WorkspaceLayout.css
│   ├── FileExplorer.tsx        # File tree component
│   └── FileExplorer.css
├── hooks/
│   └── useWorkspace.ts         # File state management
├── services/
│   └── workspaceApi.ts         # API client
├── types/
│   └── workspace.ts            # TypeScript interfaces
└── utils/
    └── constants.ts            # API config
```
