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


def warn_if_not_venv(project_root: Optional[Path] = None) -> Optional[str]:
    """Return a warning string if the active Python is not the project .venv."""
    project_root = project_root or find_project_root()
    expected = project_root / ".venv" / "bin" / "python"
    active = Path(sys.executable).resolve()
    if active != expected and expected.exists():
        return (
            f"Active python ({active}) is not project venv ({expected}). "
            "Activate .venv to avoid import/DB mismatches."
        )
    return None
