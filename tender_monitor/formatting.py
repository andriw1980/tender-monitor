from __future__ import annotations
from html import escape


def _g(r, k):
    try:
        return r[k] or ""
    except (KeyError, IndexError, TypeError):
        return getattr(r, k, "") or ""


def tender_html(r) -> str:
    lines = [f"🆕 <b>{escape(_g(r, 'title'))}</b>"]
    if _g(r, "agency"):
        lines.append(f"🏢 {escape(_g(r, 'agency'))}")
    meta = []
    if _g(r, "budget"):
        meta.append(f"💰 {escape(_g(r, 'budget'))}")
    if _g(r, "deadline"):
        meta.append(f"⏰ batas {escape(_g(r, 'deadline'))}")
    if _g(r, "stage"):
        meta.append(f"📌 {escape(_g(r, 'stage'))}")
    if meta:
        lines.append(" · ".join(meta))
    if _g(r, "keywords"):
        lines.append(f"🔎 {escape(_g(r, 'keywords'))}")
    lines.append(f"📡 {escape(_g(r, 'source'))}")
    if _g(r, "url"):
        lines.append(f'<a href="{escape(_g(r, "url"), quote=True)}">Buka pengumuman</a>')
    return "\n".join(lines)


def strip_tags(s: str) -> str:
    import re
    from html import unescape
    return unescape(re.sub(r"<[^>]+>", "", s))
