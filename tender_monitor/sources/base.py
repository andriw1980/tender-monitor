from __future__ import annotations
from ..models import Tender


class Source:
    """Satu sumber pengumuman. Subclass cukup mengisi fetch()."""
    type = "base"

    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.cfg = cfg
        self.use_filter = cfg.get("filter", True)   # false = tampilkan semua pengumuman dari sumber ini

    def fetch(self) -> list[Tender]:  # pragma: no cover
        raise NotImplementedError
