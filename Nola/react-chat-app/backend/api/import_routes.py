"""
Import API routes for conversation imports.
"""

import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import zipfile

# Add parent directories to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Nola.services.import_service import ImportService

router = APIRouter(prefix="/api/import", tags=["import"])

# Paths
WORKSPACE_PATH = Path(os.getenv("NOLA_WORKSPACE_PATH", "./workspace"))
STIMULI_PATH = Path("./Nola/Stimuli")
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "nola_imports"
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)


@router.post("/upload")
async def upload_export(
    file: UploadFile = File(...),
    platform: Optional[str] = Form(None)
):
    """
    Upload an export file or folder (as zip).
    
    Returns upload ID for tracking.
    """
    # Generate upload ID
    upload_id = f"upload_{file.filename}_{os.urandom(8).hex()}"
    upload_path = UPLOAD_TEMP_DIR / upload_id
    upload_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save uploaded file
        file_path = upload_path / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # If it's a zip, extract it
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(upload_path)
            # Remove the zip file
            file_path.unlink()
            # Use extracted folder
            extracted_folders = [p for p in upload_path.iterdir() if p.is_dir()]
            if extracted_folders:
                actual_path = extracted_folders[0]
            else:
                actual_path = upload_path
        else:
            actual_path = file_path
        
        return JSONResponse({
            "upload_id": upload_id,
            "filename": file.filename,
            "path": str(actual_path),
            "platform": platform
        })
        
    except Exception as e:
        # Cleanup on error
        if upload_path.exists():
            shutil.rmtree(upload_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/parse")
async def parse_export(
    upload_id: str = Form(...),
    platform: Optional[str] = Form(None)
):
    """
    Parse uploaded export and return preview.
    """
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Find the actual export path (folder or file)
    export_path = None
    for item in upload_path.iterdir():
        export_path = item
        break
    
    if not export_path:
        raise HTTPException(status_code=400, detail="No files found in upload")
    
    try:
        import_service = ImportService(WORKSPACE_PATH, STIMULI_PATH)
        
        # Detect platform
        if not platform:
            parser = import_service.detect_platform(export_path)
            if not parser:
                raise HTTPException(status_code=400, detail="Could not detect platform")
            platform = parser.get_platform_name()
        
        # Parse conversations (without saving)
        parser = next(p for p in import_service.parsers if p.get_platform_name().lower() == platform.lower())
        conversations = await parser.parse(export_path)
        
        # Return preview
        preview = {
            "platform": platform,
            "total_conversations": len(conversations),
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "message_count": len(conv.messages),
                    "created_at": conv.created_at.isoformat(),
                    "has_attachments": bool(conv.attachments)
                }
                for conv in conversations[:10]  # Preview first 10
            ]
        }
        
        return JSONResponse(preview)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse failed: {str(e)}")


@router.post("/commit")
async def commit_import(
    upload_id: str = Form(...),
    platform: Optional[str] = Form(None),
    organize_by_project: bool = Form(True)
):
    """
    Commit the import - convert and save conversations.
    """
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Find export path
    export_path = None
    for item in upload_path.iterdir():
        export_path = item
        break
    
    if not export_path:
        raise HTTPException(status_code=400, detail="No files found in upload")
    
    try:
        import_service = ImportService(WORKSPACE_PATH, STIMULI_PATH)
        
        # Import conversations
        result = await import_service.import_conversations(
            export_path=export_path,
            platform=platform,
            organize_by_project=organize_by_project
        )
        
        # Cleanup temp files
        shutil.rmtree(upload_path)
        
        return JSONResponse(result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/status/{upload_id}")
async def get_import_status(upload_id: str):
    """
    Check status of an upload.
    """
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        return JSONResponse({"status": "not_found"})
    
    return JSONResponse({
        "status": "ready",
        "upload_id": upload_id
    })
