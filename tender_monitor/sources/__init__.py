from .base import Source
from .html import HtmlSource
from .imap import ImapSource
from .lpse import LpseSource
from .rss import RssSource

TYPES = {"lpse": LpseSource, "rss": RssSource, "html": HtmlSource, "imap": ImapSource}


def build_sources(entries: list[dict]) -> list[Source]:
    """Ubah daftar `sources` dari config jadi objek Source. Entri lpse dengan `hosts: [a, b]`
    dipecah jadi satu sumber per host agar kegagalan satu LPSE tidak menjatuhkan yang lain."""
    out: list[Source] = []
    for e in entries:
        if e.get("enabled", True) is False:
            continue
        e = dict(e)
        typ = e.pop("type")
        name = e.pop("name")
        if typ not in TYPES:
            raise ValueError(f"tipe sumber tidak dikenal: {typ} (sumber '{name}')")
        if typ == "lpse" and "hosts" in e:
            for h in e.pop("hosts"):
                out.append(LpseSource(f"{name}/{h}", {**e, "host": h}))
        else:
            out.append(TYPES[typ](name, e))
    return out
