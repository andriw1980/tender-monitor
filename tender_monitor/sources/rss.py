from __future__ import annotations
import time

from ..models import Tender
from ..utils import parse_date, strip_html
from .base import Source


class RssSource(Source):
    """RSS/Atom. Config: url."""
    type = "rss"

    def fetch(self) -> list[Tender]:
        import feedparser
        d = feedparser.parse(self.cfg["url"], agent=self.cfg.get("user_agent", "tender-monitor/0.1"))
        if d.bozo and not d.entries:
            raise RuntimeError(f"feed tidak bisa dibaca: {getattr(d, 'bozo_exception', 'unknown')}")
        out = []
        for e in d.entries:
            pub = ""
            if getattr(e, "published_parsed", None):
                pub = time.strftime("%Y-%m-%d", e.published_parsed)
            summary = strip_html(getattr(e, "summary", ""))
            out.append(Tender(source=self.name, uid=getattr(e, "id", "") or getattr(e, "link", ""),
                              title=strip_html(getattr(e, "title", "")), agency=self.cfg.get("agency", ""),
                              published=pub, deadline=parse_date(summary) if self.cfg.get("deadline_from_summary") else "",
                              url=getattr(e, "link", ""), extra={"summary": summary}))
        return out
