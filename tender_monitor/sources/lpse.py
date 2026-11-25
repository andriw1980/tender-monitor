from __future__ import annotations
from datetime import datetime

from ..models import Tender
from ..utils import strip_html
from .base import Source


class LpseSource(Source):
    """LPSE / SPSE (INAPROC) lewat library `pyproc`.
    Mengambil N paket terbaru lalu disaring lokal dengan kata kunci.
    Config: host (kode LPSE, mis. 'kemenkeu', 'jogjakota'), jenis (tender|non_tender), limit, tahun.
    """
    type = "lpse"

    def fetch(self) -> list[Tender]:
        try:
            from pyproc import Lpse
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("library pyproc belum terpasang (pip install pyproc)") from e

        host = self.cfg["host"]
        limit = int(self.cfg.get("limit", 100))
        tahun = int(self.cfg.get("tahun", datetime.now().year))
        jenis = self.cfg.get("jenis", "tender")
        with Lpse(host, timeout=int(self.cfg.get("timeout", 20)), verify=bool(self.cfg.get("verify_ssl", False))) as lpse:
            if jenis == "non_tender":
                rows = lpse.get_paket_non_tender(start=0, length=limit, data_only=True, tahun=tahun)
                path = "nontender"
            else:
                rows = lpse.get_paket_tender(start=0, length=limit, data_only=True, tahun=tahun)
                path = "lelang"
            base = lpse.url
        return [t for t in (self._row(r, base, path) for r in rows) if t]

    def _row(self, r, base: str, path: str) -> Tender | None:
        # Kolom DataTables SPSE: [kode, nama paket, instansi, tahap, HPS, ...]. Tiap versi SPSE bisa sedikit beda,
        # maka dibaca defensif.
        if not r or len(r) < 2:
            return None
        g = lambda i: strip_html(r[i]) if len(r) > i and r[i] is not None else ""
        uid = g(0)
        suffix = "pengumumanlelang" if path == "lelang" else "pengumumanpl"
        return Tender(source=self.name, uid=uid, title=g(1), agency=g(2), stage=g(3), budget=g(4),
                      url=f"{base}/{path}/{uid}/{suffix}")
