from __future__ import annotations
import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def match_keywords(text: str, include: list[str], exclude: list[str] | None = None) -> list[str] | None:
    """Kembalikan daftar kata kunci yang cocok.
    - None  : tidak lolos (kena exclude, atau include diisi tapi tak ada yang cocok)
    - []    : lolos tanpa kata kunci (include kosong = tampilkan semua)
    - [...] : lolos, dengan kata kunci yang cocok
    Kata kunci dicocokkan sebagai kata utuh (awalan), tanpa membedakan huruf besar/kecil.
    """
    t = _norm(text)
    for ex in exclude or []:
        if _pat(ex).search(t):
            return None
    if not include:
        return []
    hits = [kw for kw in include if _pat(kw).search(t)]
    return hits or None


def _pat(kw: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(_norm(kw)), re.I)
