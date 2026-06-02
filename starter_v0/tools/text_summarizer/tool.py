from __future__ import annotations

import re
from typing import Any

from tools._shared import err


def _split_sentences(text: str) -> list[str]:
    # Lightweight sentence splitter; good enough for eval + deterministic behavior.
    chunks = re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip())
    return [c.strip() for c in chunks if c and c.strip()]


def text_summarizer(text: str = "", max_sentences: int = 3, max_chars: int = 600) -> dict[str, Any]:
    """
    Local deterministic summarizer.
    - Picks the first N sentences up to max_chars.
    """
    try:
        max_sentences = int(max_sentences or 3)
        max_chars = int(max_chars or 600)
        if max_sentences < 1:
            max_sentences = 1
        if max_chars < 50:
            max_chars = 50

        sentences = _split_sentences(text)
        picked: list[str] = []
        total = 0
        for s in sentences:
            add_len = len(s) + (1 if picked else 0)
            if len(picked) >= max_sentences:
                break
            if total + add_len > max_chars and picked:
                break
            picked.append(s)
            total += add_len

        summary = " ".join(picked).strip()
        return {
            "tool": "text_summarizer",
            "max_sentences": max_sentences,
            "max_chars": max_chars,
            "summary": summary,
        }
    except Exception as exc:
        return err("text_summarizer", exc)
