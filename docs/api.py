"""
Docs API - Serve markdown documentation files
==============================================
Provides read-only access to documentation (.md files) for the frontend.
Scans the entire project tree for .md files, excluding _archive directories.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from pathlib import Path

router = APIRouter(prefix="/api/docs", tags=["docs"])

# Project root is two levels up from this file (docs/api.py -> AI_OS/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories to exclude from scanning
EXCLUDE_DIRS = {
    "_archive", "__pycache__", ".git", "node_modules", 
    ".venv", "venv", "env", ".pytest_cache", "dist", "build",
    ".next", ".turbo", "coverage", ".mypy_cache"
}

# Files to exclude
EXCLUDE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}


def build_node(dir_path: Path, rel_prefix: str = "", root_name: str = "AI_OS") -> Dict[str, Any]:
    """Build a nested directory node structure for .md files only."""
    node = {
        "name": dir_path.name if rel_prefix else root_name,
        "path": rel_prefix,
        "is_folder": True,
        "children": []
    }
    try:
        for item in sorted(dir_path.iterdir()):
            # Skip hidden files/dirs and excluded directories
            if item.name.startswith(".") or item.name in EXCLUDE_DIRS:
                continue
            
            # Skip excluded files
            if item.name in EXCLUDE_FILES:
                continue

            item_rel = f"{rel_prefix}{item.name}" if rel_prefix else item.name

            if item.is_dir():
                # Recursively build child node
                child_node = build_node(item, item_rel + "/", root_name)
                # Only include folder if it has .md files (directly or nested)
                if child_node["children"]:
                    node["children"].append(child_node)
            elif item.is_file() and item.suffix.lower() == ".md":
                node["children"].append({
                    "name": item.name,
                    "path": item_rel,
                    "size": item.stat().st_size,
                    "is_folder": False,
                })
    except PermissionError:
        pass
    return node


def count_files(n: Dict[str, Any]) -> int:
    """Count markdown files in tree."""
    c = 0
    for ch in n.get("children", []):
        if ch.get("is_folder"):
            c += count_files(ch)
        else:
            c += 1
    return c


@router.get("")
async def list_docs() -> Dict[str, Any]:
    """
    List all markdown files in the entire project.
    Returns a nested tree structure excluding _archive directories.
    """
    if not PROJECT_ROOT.exists():
        return {"files": [], "error": f"Project root not found: {PROJECT_ROOT}"}
    
    tree = build_node(PROJECT_ROOT, "", PROJECT_ROOT.name)

    return {
        "tree": tree,
        "root": str(PROJECT_ROOT),
        "count": count_files(tree),
    }


@router.get("/content")
async def get_doc_content(path: str = Query(..., description="Relative path to the doc file")) -> Dict[str, Any]:
    """
    Get the content of a specific markdown file.
    Path is relative to the project root.
    """
    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    file_path = PROJECT_ROOT / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only .md files are allowed")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            "path": path,
            "name": file_path.name,
            "content": content,
            "size": len(content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
