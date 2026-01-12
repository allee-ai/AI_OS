"""
Docs API - Serve markdown documentation files
==============================================
Provides read-only access to documentation (.md files) for the frontend.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
from pathlib import Path

router = APIRouter(prefix="/api/docs", tags=["docs"])

# The docs directory - relative to the AI_OS root
DOCS_ROOT = Path(__file__).parent.parent.parent.parent.parent / "docs"


@router.get("")
async def list_docs() -> Dict[str, Any]:
    """
    List all markdown files in the docs directory.
    Returns a flat list of relative paths.
    """
    if not DOCS_ROOT.exists():
        return {"files": [], "error": f"Docs directory not found: {DOCS_ROOT}"}
    
    def build_node(dir_path: Path, rel_prefix: str = "") -> Dict[str, Any]:
        """Build a nested directory node structure."""
        node = {"name": dir_path.name if rel_prefix else "docs", "path": rel_prefix, "is_folder": True, "children": []}
        try:
            for item in sorted(dir_path.iterdir()):
                if item.is_dir() and item.name.startswith((".", "_", "__")):
                    continue

                item_rel = f"{rel_prefix}{item.name}" if rel_prefix else item.name

                if item.is_dir():
                    node["children"].append(build_node(item, item_rel + "/"))
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

    tree = build_node(DOCS_ROOT, "")

    # also return a flat count for convenience
    def count_files(n: Dict[str, Any]) -> int:
        c = 0
        for ch in n.get("children", []):
            if ch.get("is_folder"):
                c += count_files(ch)
            else:
                c += 1
        return c

    return {
        "tree": tree,
        "root": str(DOCS_ROOT),
        "count": count_files(tree),
    }


@router.get("/content")
async def get_doc_content(path: str = Query(..., description="Relative path to the doc file")) -> Dict[str, Any]:
    """
    Get the content of a specific markdown file.
    Path is relative to the docs directory.
    """
    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    file_path = DOCS_ROOT / path
    
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
