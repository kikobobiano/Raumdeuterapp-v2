"""Safe double-quote quoting for DuckDB column identifiers."""

from __future__ import annotations


def q_ident(name: str) -> str:
    if any(c in name for c in ('"', ";", "--")):
        raise ValueError(f"invalid column name: {name!r}")
    return f'"{name}"'
