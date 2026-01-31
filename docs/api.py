"""
Docs API - Serve markdown documentation files
==============================================
Provides read-only access to documentation (.md files) for the frontend.
Scans the entire project tree for .md files, excluding _archive directories.
Includes aggregation function to build unified docs from module READMEs.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Tuple
from pathlib import Path
import re

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


# =============================================================================
# Documentation Aggregation
# =============================================================================

# Modules to scan for documentation sections
MODULES: List[Tuple[str, str, str]] = [
    # (path, module_id, display_name)
    ("agent/threads/identity", "identity", "Identity Thread"),
    ("agent/threads/philosophy", "philosophy", "Philosophy Thread"),
    ("agent/threads/log", "log", "Log Thread"),
    ("agent/threads/form", "form", "Form Thread"),
    ("agent/threads/reflex", "reflex", "Reflex Thread"),
    ("agent/threads/linking_core", "linking_core", "Linking Core"),
    ("agent/subconscious", "subconscious", "Subconscious"),
    ("agent/subconscious/temp_memory", "temp_memory", "Temp Memory"),
    ("agent/services", "services", "Services"),
    ("chat", "chat", "Chat"),
    ("Feeds", "feeds", "Feeds"),
    ("workspace", "workspace", "Workspace"),
    ("finetune", "finetune", "Finetune"),
    ("eval", "eval", "Eval"),
]


def extract_section(readme_path: Path, section: str, module: str) -> str:
    """Extract a marked section from a README file."""
    if not readme_path.exists():
        return ""
    
    content = readme_path.read_text(encoding="utf-8")
    pattern = f"<!-- {section}:{module} -->(.*?)<!-- /{section}:{module} -->"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_description(readme_path: Path) -> str:
    """Extract the Description section from a README."""
    if not readme_path.exists():
        return ""
    
    content = readme_path.read_text(encoding="utf-8")
    # Match ## Description until next ## or end
    match = re.search(r"## Description\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    return match.group(1).strip() if match else ""


def aggregate_architecture() -> str:
    """Build unified ARCHITECTURE.md from module sections."""
    lines = [
        "# Architecture Reference",
        "",
        "> _Auto-generated from module READMEs. Edit documentation at the module level._",
        "",
        "---",
        ""
    ]
    
    for path, module, name in MODULES:
        readme = PROJECT_ROOT / path / "README.md"
        content = extract_section(readme, "ARCHITECTURE", module)
        if content:
            lines.append(f"## {name}")
            lines.append(f"_Source: [{path}/README.md]({path}/README.md)_")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def aggregate_roadmap() -> str:
    """Build unified MODULE_ROADMAP.md from module sections."""
    lines = [
        "# Module Roadmap",
        "",
        "> _Auto-generated from module READMEs. Edit tasks at the module level._",
        "",
        "---",
        ""
    ]
    
    for path, module, name in MODULES:
        readme = PROJECT_ROOT / path / "README.md"
        content = extract_section(readme, "ROADMAP", module)
        if content:
            lines.append(f"## {name}")
            lines.append(f"_Source: [{path}/README.md]({path}/README.md)_")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def aggregate_changelog() -> str:
    """Build unified CHANGELOG.md from module sections."""
    lines = [
        "# Changelog",
        "",
        "> _Auto-generated from module READMEs. Log changes at the module level._",
        "",
        "---",
        ""
    ]
    
    for path, module, name in MODULES:
        readme = PROJECT_ROOT / path / "README.md"
        content = extract_section(readme, "CHANGELOG", module)
        if content:
            lines.append(f"## {name}")
            lines.append(f"_Source: [{path}/README.md]({path}/README.md)_")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def get_module_status() -> List[Dict[str, Any]]:
    """Get documentation status for all modules."""
    status = []
    for path, module, name in MODULES:
        readme = PROJECT_ROOT / path / "README.md"
        has_readme = readme.exists()
        
        has_arch = bool(extract_section(readme, "ARCHITECTURE", module)) if has_readme else False
        has_roadmap = bool(extract_section(readme, "ROADMAP", module)) if has_readme else False
        has_changelog = bool(extract_section(readme, "CHANGELOG", module)) if has_readme else False
        
        status.append({
            "path": path,
            "module": module,
            "name": name,
            "has_readme": has_readme,
            "has_architecture": has_arch,
            "has_roadmap": has_roadmap,
            "has_changelog": has_changelog,
            "complete": has_readme and has_arch and has_roadmap and has_changelog
        })
    
    return status


@router.get("/aggregate/status")
async def get_aggregation_status() -> Dict[str, Any]:
    """
    Get documentation status for all modules.
    Shows which modules have the required sections.
    """
    status = get_module_status()
    complete = sum(1 for s in status if s["complete"])
    
    return {
        "modules": status,
        "total": len(status),
        "complete": complete,
        "incomplete": len(status) - complete
    }


def update_doc_section(doc_path: Path, section: str, module: str, content: str) -> bool:
    """
    Update a section in a root doc file with content from a module.
    Looks for <!-- INCLUDE:module:SECTION --> ... <!-- /INCLUDE:module:SECTION --> markers.
    Returns True if updated, False if marker not found.
    """
    if not doc_path.exists():
        return False
    
    doc_content = doc_path.read_text(encoding="utf-8")
    
    # Pattern: <!-- INCLUDE:identity:ARCHITECTURE --> ... <!-- /INCLUDE:identity:ARCHITECTURE -->
    pattern = f"(<!-- INCLUDE:{module}:{section} -->)(.*?)(<!-- /INCLUDE:{module}:{section} -->)"
    
    if not re.search(pattern, doc_content, re.DOTALL):
        return False
    
    # Build replacement with source link
    module_info = next((m for m in MODULES if m[1] == module), None)
    if module_info:
        path, _, name = module_info
        header = f"\n_Source: [{path}/README.md]({path}/README.md)_\n\n"
    else:
        header = "\n"
    
    replacement = f"\\1{header}{content}\n\\3"
    new_content = re.sub(pattern, replacement, doc_content, flags=re.DOTALL)
    
    if new_content != doc_content:
        doc_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def sync_module_to_root(module: str) -> Dict[str, bool]:
    """
    Sync a single module's documentation to root docs.
    Pulls ARCHITECTURE, ROADMAP, CHANGELOG from module README
    and updates corresponding sections in root docs.
    """
    module_info = next((m for m in MODULES if m[1] == module), None)
    if not module_info:
        return {"error": f"Unknown module: {module}"}
    
    path, module_id, name = module_info
    readme = PROJECT_ROOT / path / "README.md"
    
    results = {}
    
    # Sync Architecture
    arch_content = extract_section(readme, "ARCHITECTURE", module_id)
    if arch_content:
        results["architecture"] = update_doc_section(
            PROJECT_ROOT / "docs" / "ARCHITECTURE.md",
            "ARCHITECTURE", module_id, arch_content
        )
    else:
        results["architecture"] = False
    
    # Sync Roadmap
    roadmap_content = extract_section(readme, "ROADMAP", module_id)
    if roadmap_content:
        results["roadmap"] = update_doc_section(
            PROJECT_ROOT / "docs" / "ROADMAP.md",
            "ROADMAP", module_id, roadmap_content
        )
    else:
        results["roadmap"] = False
    
    # Sync Changelog
    changelog_content = extract_section(readme, "CHANGELOG", module_id)
    if changelog_content:
        results["changelog"] = update_doc_section(
            PROJECT_ROOT / "docs" / "CHANGELOG.md",
            "CHANGELOG", module_id, changelog_content
        )
    else:
        results["changelog"] = False
    
    return results


def sync_all_modules() -> Dict[str, Any]:
    """Sync all modules to root docs."""
    results = {}
    for path, module, name in MODULES:
        results[module] = sync_module_to_root(module)
    return results


@router.post("/aggregate/refresh")
async def refresh_aggregated_docs() -> Dict[str, Any]:
    """
    Sync all module documentation to root docs.
    Updates sections in existing ARCHITECTURE.md, MODULE_ROADMAP.md, CHANGELOG.md
    by replacing content between INCLUDE markers.
    """
    results = sync_all_modules()
    
    updated = sum(
        1 for module_results in results.values() 
        if isinstance(module_results, dict) and any(module_results.values())
    )
    
    return {
        "message": f"Synced {updated} modules to root docs",
        "results": results,
        "status": get_module_status()
    }


@router.post("/aggregate/sync/{module}")
async def sync_single_module(module: str) -> Dict[str, Any]:
    """
    Sync a single module's documentation to root docs.
    Call this when a specific module README changes.
    """
    results = sync_module_to_root(module)
    
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
    
    return {
        "message": f"Synced {module} to root docs",
        "module": module,
        "results": results
    }


# =============================================================================
# File Watcher for Auto-Sync
# =============================================================================

_watcher_running = False
_watcher_thread = None

def get_module_from_path(file_path: str) -> str:
    """Extract module ID from a file path."""
    for path, module, name in MODULES:
        if path in file_path and file_path.endswith("README.md"):
            return module
    return None


def start_doc_watcher():
    """Start watching module READMEs for changes."""
    global _watcher_running, _watcher_thread
    
    if _watcher_running:
        return {"status": "already_running"}
    
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import threading
        
        class DocChangeHandler(FileSystemEventHandler):
            def __init__(self):
                self.last_sync = {}
            
            def on_modified(self, event):
                if event.is_directory:
                    return
                
                # Debounce - don't sync same file within 1 second
                import time
                now = time.time()
                if event.src_path in self.last_sync:
                    if now - self.last_sync[event.src_path] < 1:
                        return
                
                module = get_module_from_path(event.src_path)
                if module:
                    print(f"[docs] Auto-syncing {module} (file changed)")
                    sync_module_to_root(module)
                    self.last_sync[event.src_path] = now
        
        observer = Observer()
        handler = DocChangeHandler()
        
        # Watch all module directories
        for path, module, name in MODULES:
            watch_path = PROJECT_ROOT / path
            if watch_path.exists():
                observer.schedule(handler, str(watch_path), recursive=False)
        
        def run_watcher():
            observer.start()
            try:
                while _watcher_running:
                    import time
                    time.sleep(1)
            finally:
                observer.stop()
                observer.join()
        
        _watcher_running = True
        _watcher_thread = threading.Thread(target=run_watcher, daemon=True)
        _watcher_thread.start()
        
        return {"status": "started", "watching": len(MODULES)}
        
    except ImportError:
        return {"status": "error", "message": "watchdog not installed. Run: pip install watchdog"}


def stop_doc_watcher():
    """Stop the file watcher."""
    global _watcher_running
    _watcher_running = False
    return {"status": "stopped"}


@router.post("/watcher/start")
async def api_start_watcher() -> Dict[str, Any]:
    """Start the file watcher for auto-sync."""
    return start_doc_watcher()


@router.post("/watcher/stop")
async def api_stop_watcher() -> Dict[str, Any]:
    """Stop the file watcher."""
    return stop_doc_watcher()


@router.get("/watcher/status")
async def api_watcher_status() -> Dict[str, Any]:
    """Get file watcher status."""
    return {"running": _watcher_running}


@router.get("/aggregate/preview/{doc_type}")
async def preview_aggregated_doc(doc_type: str) -> Dict[str, Any]:
    """
    Preview aggregated documentation without writing to disk.
    doc_type: 'architecture', 'roadmap', or 'changelog'
    """
    if doc_type == "architecture":
        content = aggregate_architecture()
    elif doc_type == "roadmap":
        content = aggregate_roadmap()
    elif doc_type == "changelog":
        content = aggregate_changelog()
    else:
        raise HTTPException(status_code=400, detail="Invalid doc_type. Use: architecture, roadmap, changelog")
    
    return {
        "type": doc_type,
        "content": content,
        "size": len(content)
    }
