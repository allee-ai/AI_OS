"""Common path helpers to make Nola imports and DB resolution consistent.

Uses pyproject.toml as the anchor for the project root so services and
backend code can import `Nola.*` without hand-rolled sys.path tweaks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

PYPROJECT = "pyproject.toml"


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk upward from `start` (or this file) to locate pyproject.toml."""
    start = start or Path(__file__).resolve()
    for candidate in [start] + list(start.parents):
        if (candidate / PYPROJECT).exists():
            return candidate
    return start.parent


def ensure_project_root_on_path(start: Optional[Path] = None) -> Path:
    """Ensure the project root is on sys.path; return the root Path."""
    root = find_project_root(start)
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def ensure_nola_root_on_path(start: Optional[Path] = None) -> Path:
    """Ensure the Nola package directory is on sys.path; return it."""
    project_root = ensure_project_root_on_path(start)
    nola_root = project_root / "Nola"
    if nola_root.exists():
        nola_str = str(nola_root)
        if nola_str not in sys.path:
            sys.path.insert(0, nola_str)
    return nola_root


# Track if warning has been shown to avoid spam
_venv_warning_shown = False

def warn_if_not_venv(project_root: Optional[Path] = None) -> Optional[str]:
    """Return a warning string if not running from the project's virtual environment.
    
    Only returns the warning once per process to avoid log spam.
    Checks if the venv's site-packages is in sys.path (more reliable than comparing executables).
    """
    global _venv_warning_shown
    if _venv_warning_shown:
        return None
    
    project_root = project_root or find_project_root()
    venv_site_packages = project_root / ".venv" / "lib"
    
    # Check if venv's lib directory is in any sys.path entry
    venv_in_path = any(str(venv_site_packages) in p for p in sys.path)
    
    if not venv_in_path and venv_site_packages.exists():
        _venv_warning_shown = True
        return (
            f"Project venv ({project_root / '.venv'}) not detected in sys.path. "
            "Activate .venv or use 'uv run' to avoid import/DB mismatches."
        )
    return None
