"""Path helpers for runnable scripts invoked as ``python scripts/<name>.py``.

``sys.path[0]`` is the ``scripts/`` directory, so this package can live here without
having the monorepo root on PYTHONPATH upfront.
"""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root(script_path: str | Path) -> Path:
    """Resolve repo root via ``utils/repo_root.repo_root``, bootstrapping ``sys.path``.

    Parameters
    ----------
    script_path:
        Caller should pass ``__file__``.
    """

    sf = Path(script_path).resolve()
    for cand in sf.parents:
        if (cand / "utils" / "repo_root.py").is_file():
            s = str(cand)
            if s not in sys.path:
                sys.path.insert(0, s)
            break
    else:
        raise RuntimeError(
            "Não foi possível localizar raumdeuterappv2 (esperado utils/repo_root.py). "
            "Define RAUMDEUTER_REPO_ROOT ou corre a partir do checkout."
        )

    # Local import once repo root is on sys.path (``utils.repo_root`` has the marker logic).
    from utils.repo_root import repo_root as _root

    return _root(sf)
