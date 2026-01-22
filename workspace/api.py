"""
Workspace API - Virtual Filesystem endpoints
============================================
DB-backed file storage with search and LLM-ready chunking.

Endpoints:
  GET    /api/workspace/files       - List directory
  GET    /api/workspace/file        - Get file content
  POST   /api/workspace/file        - Create/update file
  DELETE /api/workspace/file        - Delete file
  POST   /api/workspace/folder      - Create folder
  POST   /api/workspace/move        - Move/rename file
  GET    /api/workspace/search      - Full-text search
  GET    /api/workspace/stats       - Workspace statistics
  POST   /api/workspace/index       - Index file for search
  GET    /api/workspace/chunks      - Get LLM-ready chunks
  POST   /api/workspace/upload      - Upload binary file
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import sys

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .schema import (
    create_file,
    get_file,
    list_directory,
    delete_file,
    move_file,
    ensure_folder,
    search_files,
    chunk_file,
    get_file_chunks,
    get_workspace_stats,
    normalize_path,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# =============================================================================
# Models
# =============================================================================

class FileCreate(BaseModel):
    path: str
    content: str
    mime_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FolderCreate(BaseModel):
    path: str


class FileMove(BaseModel):
    old_path: str
    new_path: str


class FileInfo(BaseModel):
    path: str
    name: str
    is_folder: bool
    mime_type: Optional[str]
    size: int
    modified_at: Optional[str]


class SearchResult(BaseModel):
    path: str
    name: str
    mime_type: Optional[str]
    size: int
    snippet: Optional[str]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/files", response_model=List[FileInfo])
async def list_files(path: str = "/"):
    """List contents of a directory."""
    try:
        files = list_directory(path)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file")
async def get_file_content(path: str):
    """Get file content and metadata."""
    file = get_file(path)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file["is_folder"]:
        raise HTTPException(status_code=400, detail="Cannot get content of folder")
    
    # Return file with content
    return Response(
        content=file["content"],
        media_type=file["mime_type"],
        headers={
            "X-File-Path": file["path"],
            "X-File-Size": str(file["size"]),
            "X-File-Hash": file["hash"] or "",
        }
    )


@router.post("/file")
async def create_or_update_file(request: FileCreate):
    """Create or update a file."""
    try:
        content = request.content.encode('utf-8')
        result = create_file(
            path=request.path,
            content=content,
            mime_type=request.mime_type,
            metadata=request.metadata
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form("/")
):
    """Upload a binary file."""
    try:
        content = await file.read()
        
        # If path is a folder, append filename
        target_path = normalize_path(path)
        existing = get_file(target_path)
        if target_path.endswith('/') or (existing and existing.get("is_folder")):
            target_path = target_path.rstrip('/') + '/' + file.filename
        
        result = create_file(
            path=target_path,
            content=content,
            mime_type=file.content_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/file")
async def delete_file_endpoint(path: str, recursive: bool = False):
    """Delete a file or folder."""
    try:
        success = delete_file(path, recursive=recursive)
        if not success:
            raise HTTPException(status_code=404, detail="File not found")
        return {"deleted": path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folder")
async def create_folder(request: FolderCreate):
    """Create a folder (and any parent folders)."""
    try:
        ensure_folder(request.path)
        return {"created": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move")
async def move_file_endpoint(request: FileMove):
    """Move or rename a file/folder."""
    try:
        success = move_file(request.old_path, request.new_path)
        if not success:
            raise HTTPException(status_code=404, detail="Source file not found")
        return {"moved": request.old_path, "to": request.new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[SearchResult])
async def search(q: str, limit: int = 20):
    """Full-text search across file contents."""
    try:
        results = search_files(q, limit=limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index_file(path: str):
    """Index a file for search (chunks it for LLM consumption)."""
    file = get_file(path)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file["is_folder"]:
        raise HTTPException(status_code=400, detail="Cannot index folder")
    
    try:
        chunk_count = chunk_file(file["id"])
        return {"indexed": path, "chunks": chunk_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks")
async def get_chunks(path: str):
    """Get pre-chunked content for LLM consumption."""
    chunks = get_file_chunks(path)
    if not chunks:
        # Try to chunk on-the-fly
        file = get_file(path)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        chunk_file(file["id"])
        chunks = get_file_chunks(path)
    
    return {"path": path, "chunks": chunks, "count": len(chunks)}


@router.get("/stats")
async def workspace_stats():
    """Get workspace statistics."""
    return get_workspace_stats()


@router.get("/info")
async def workspace_info():
    """Get workspace info and status."""
    stats = get_workspace_stats()
    return {
        "name": "Nola Workspace",
        "type": "sqlite-vfs",
        "stats": stats,
        "features": [
            "full-text-search",
            "llm-chunking",
            "metadata",
            "versioning-ready"
        ]
    }
