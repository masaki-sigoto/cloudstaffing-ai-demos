"""Text normalization (spec §5.6)."""
from __future__ import annotations
import re
import unicodedata


def normalize_text(s: str) -> str:
    """NFKC + strip + compress internal whitespace. ￥/¥ unified to ¥."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    # 全角￥ → ¥ (NFKC already converts; keep defensive)
    s = s.replace("￥", "¥")
    # Collapse consecutive whitespace to single half-width space
    s = re.sub(r"\s+", " ", s).strip()
    return s
