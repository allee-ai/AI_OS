"""
Workspace API - File management endpoints for the Nola workspace.

SECURITY: All file operations are sandboxed to WORKSPACE_ROOT.
No operations can escape this directory.

Endpoints:
  GET    /api/workspace/files      - List files/folders
  GET    /api/workspace/info       - Workspace info
  POST   /api/workspace/folder     - Create folder
  POST   /api/workspace/upload     - Upload file
  GET    /api/workspace/download/  - Download file
  DELETE /api/workspace/files/     - Delete file/folder
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from datetime import datetime
import shutil
import os
import uuid

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

# Dedicated workspace directory - completely isolated from Nola core
# Nola/workspace/api.py -> Nola -> AI_OS -> workspace
WORKSPACE_ROOT = Path(os.getenv("NOLA_WORKSPACE_PATH", 
    Path(__file__).parent.parent.parent / "workspace"))

# Welcome file content
WELCOME_CONTENT = """# Welcome to Nola Workspace! 🧠

This is your personal file storage area. Everything here is:
- **Local-first**: Files stay on your machine
- **Private**: No cloud sync unless you configure it
- **Yours**: Full control over your data

## What can you do here?
- 📤 Upload files to share with Nola
- 📁 Create folders to organize your content
- 📄 Store documents, notes, and references
- 🔗 Link files to conversations (coming soon)

## Tips
- Drag and drop files to upload
- Click folders to navigate
- Use the breadcrumb to go back

---
*This workspace is sandboxed - Nola cannot access files outside this folder.*
"""


# =============================================================================
# Pydantic Models
# =============================================================================

class FileItem(BaseModel):
    id: str
    name: str
    path: str
    type: str  # "file" or "folder"
    size: Optional[int] = None
    mimeType: Optional[str] = None
    createdAt: str
    updatedAt: str
    parentId: Optional[str] = None


class CreateFolderRequest(BaseModel):
    name: str
    parentPath: str


# =============================================================================
# Helpers
# =============================================================================

def ensure_workspace():
    """Ensure workspace directory exists with welcome file."""
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Create welcome file if workspace is empty
    welcome_file = WORKSPACE_ROOT / "Welcome.md"
    if not welcome_file.exists():
        welcome_file.write_text(WELCOME_CONTENT, encoding="utf-8")


def is_path_safe(path: Path) -> bool:
    """Check if a path is safely within the workspace root.
    
    This is the CRITICAL security check that prevents directory traversal.
    """
    try:
        resolved_path = path.resolve()
        resolved_root = WORKSPACE_ROOT.resolve()
        resolved_path.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def get_mime_type(path: Path) -> str:
    """Get MIME type based on file extension."""
    ext = path.suffix.lower()
    mime_map = {
        '.json': 'application/json',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.py': 'text/x-python',
        '.js': 'text/javascript',
        '.ts': 'text/typescript',
        '.tsx': 'text/typescript-jsx',
        '.jsx': 'text/javascript-jsx',
        '.html': 'text/html',
        '.css': 'text/css',
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.mp4': 'video/mp4',
        '.zip': 'application/zip',
    }
    return mime_map.get(ext, 'application/octet-stream')


def path_to_file_item(path: Path, parent_path: str = "/") -> FileItem:
    """Convert a Path to a FileItem."""
    stat = path.stat()
    rel_path = "/" + str(path.relative_to(WORKSPACE_ROOT))
    
    return FileItem(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, rel_path)),
        name=path.name,
        path=rel_path,
        type="folder" if path.is_dir() else "file",
        size=stat.st_size if path.is_file() else None,
        mimeType=get_mime_type(path) if path.is_file() else None,
        createdAt=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        updatedAt=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        parentId=str(uuid.uuid5(uuid.NAMESPACE_URL, parent_path)) if parent_path != "/" else None
    )


def validate_path(rel_path: str) -> Path:
    """Validate and resolve a path, preventing directory traversal.
    
    SECURITY: This function ensures all paths stay within WORKSPACE_ROOT.
    """
    clean_path = os.path.normpath(rel_path).lstrip("/")
    
    if ".." in rel_path or ".." in clean_path:
        raise HTTPException(status_code=403, detail="Access denied: path traversal not allowed")
    
    full_path = WORKSPACE_ROOT / clean_path
    
    if not is_path_safe(full_path):
        raise HTTPException(status_code=403, detail="Access denied: path outside workspace")
    
    return full_path


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/files")
async def list_files(path: str = "/"):
    """List files and folders in a directory."""
    ensure_workspace()
    
    if path == "/" or path == "":
        target = WORKSPACE_ROOT
        parent = "/"
    else:
        target = validate_path(path)
        parent = path
    
    if not target.exists():
        return []
    
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    files = []
    items = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    
    for item in items:
        if item.name.startswith('.') or item.name == '__pycache__':
            continue
        try:
            files.append(path_to_file_item(item, parent))
        except Exception:
            continue
    
    return files


@router.get("/info")
async def workspace_info():
    """Get workspace information."""
    ensure_workspace()
    return {
        "root": str(WORKSPACE_ROOT.resolve()),
        "exists": WORKSPACE_ROOT.exists(),
        "sandboxed": True,
        "message": "All file operations are restricted to this directory"
    }


@router.post("/folder")
async def create_folder(request: CreateFolderRequest):
    """Create a new folder."""
    ensure_workspace()
    
    if "/" in request.name or "\\" in request.name or ".." in request.name:
        raise HTTPException(status_code=400, detail="Invalid folder name")
    
    parent = validate_path(request.parentPath) if request.parentPath != "/" else WORKSPACE_ROOT
    new_folder = parent / request.name
    
    if not is_path_safe(new_folder):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if new_folder.exists():
        raise HTTPException(status_code=409, detail="Folder already exists")
    
    new_folder.mkdir(parents=True, exist_ok=True)
    
    return path_to_file_item(new_folder, request.parentPath)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    targetPath: str = Form("/")
):
    """Upload a file to the workspace."""
    ensure_workspace()
    
    filename = os.path.basename(file.filename)
    if ".." in filename or not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    target_dir = validate_path(targetPath) if targetPath != "/" else WORKSPACE_ROOT
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / filename
    
    if not is_path_safe(file_path):
        raise HTTPException(status_code=403, detail="Access denied")
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return path_to_file_item(file_path, targetPath)


@router.get("/download/{file_id}")
async def download_file(file_id: str, path: str = None):
    """Download a file from the workspace."""
    if not path:
        raise HTTPException(status_code=400, detail="Path parameter required")
    
    file_path = validate_path(path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=get_mime_type(file_path)
    )


@router.delete("/files/{file_id}")
async def delete_item(file_id: str, path: str = None):
    """Delete a file or folder."""
    if not path:
        raise HTTPException(status_code=400, detail="Path parameter required")
    
    target = validate_path(path)
    
    if not target.exists():
        raise HTTPException(status_code=404, detail="Item not found")
    
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    
    return {"message": "Deleted", "id": file_id}
