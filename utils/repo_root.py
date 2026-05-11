"""Resolve the monorepo root for pipelines and tooling (symlink-aware)."""

from __future__ import annotations

import os
from pathlib import Path

# Primary marker relative to repo root (works regardless of symlinked `data/`).
_MARKER = Path("scripts") / "download_data.py"


def repo_root(anchor: Path | None = None) -> Path:
    """Return the repository root containing ``scripts/download_data.py``.

    Resolution order:

    1. Environment variable ``RAUMDEUTER_REPO_ROOT`` (must contain the marker).
    2. Walk parents of ``anchor`` (default: this file → ``utils/repo_root.py``).
    """
    raw = os.environ.get("RAUMDEUTER_REPO_ROOT")
    if raw:
        root = Path(raw).expanduser().resolve()
        if root.is_dir() and (root / _MARKER).is_file():
            return root

    start = anchor.resolve() if anchor is not None else Path(__file__).resolve()
    for p in start.parents:
        if (p / _MARKER).is_file():
            return p

    raise FileNotFoundError(
        "Raiz do repositório não encontrada (esperado scripts/download_data.py). "
        "Define RAUMDEUTER_REPO_ROOT para o checkout raumdeuterappv2 ou corre a partir dessa pasta."
    )


def ensure_repo_on_syspath(for_file: Path) -> Path:
    """Insert repo root at the front of ``sys.path`` so ``import utils.*`` works."""
    import sys

    root = repo_root(for_file)
    sroot = os.fspath(root)
    if sroot not in sys.path:
        sys.path.insert(0, sroot)
    return root
