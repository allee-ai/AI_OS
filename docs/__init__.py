"""
Docs Module
-----------
Serve markdown documentation files via API.
Includes documentation aggregation from module READMEs.

Features:
- Serve .md files to frontend
- Aggregate module docs into root docs
- File watcher for auto-sync on change

Exports:
- router: FastAPI router for docs endpoints
- sync_module_to_root: Sync one module's docs to root
- sync_all_modules: Sync all modules
- start_doc_watcher: Start auto-sync on file changes
- stop_doc_watcher: Stop the watcher
"""

from .api import (
    router,
    aggregate_architecture,
    aggregate_roadmap,
    aggregate_changelog,
    get_module_status,
    sync_module_to_root,
    sync_all_modules,
    start_doc_watcher,
    stop_doc_watcher,
    MODULES,
)

__all__ = [
    "router",
    "aggregate_architecture",
    "aggregate_roadmap", 
    "aggregate_changelog",
    "get_module_status",
    "sync_module_to_root",
    "sync_all_modules",
    "start_doc_watcher",
    "stop_doc_watcher",
    "MODULES",
]
