"""Accent-folding word search — port of legacy utils/text_search.py."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


def strip_accents(text: str) -> str:
    if not text:
        return ""
    norm = unicodedata.normalize("NFD", str(text))
    return "".join(c for c in norm if unicodedata.category(c) != "Mn")


def _norm(t: str) -> str:
    return strip_accents(t).casefold().strip()


def _query_tokens(query: str) -> list[str]:
    return [_norm(p) for p in re.split(r"\s+", query.strip()) if _norm(p)]


def _option_tokens(option: str) -> list[str]:
    base = strip_accents(str(option))
    return [m.group(0).casefold() for m in _WORD_RE.finditer(base) if m.group(0).strip("'")]


def matches(option: str, query: str) -> bool:
    qts = _query_tokens(query)
    if not qts:
        return True
    ows = _option_tokens(option)
    if not ows:
        return False
    return all(any(ow == qt or ow.startswith(qt) for ow in ows) for qt in qts)


def filter_options(options: Sequence[str], query: str) -> list[str]:
    if not query or not str(query).strip():
        return list(options)
    return [o for o in options if matches(o, str(query))]
