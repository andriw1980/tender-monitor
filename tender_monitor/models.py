from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


@dataclass
class Tender:
    source: str                 # nama sumber di config, mis. "lpse-kemenkeu"
    uid: str                    # ID unik di sumbernya (kode paket / link)
    title: str
    agency: str = ""
    budget: str = ""            # pagu/HPS apa adanya (teks)
    published: str = ""
    deadline: str = ""          # batas pendaftaran, format YYYY-MM-DD bila diketahui
    stage: str = ""
    url: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Kunci dedup: sumber + uid. Bila uid kosong, pakai hash judul+instansi."""
        uid = self.uid or hashlib.sha1(f"{self.title}|{self.agency}".encode()).hexdigest()[:16]
        return f"{self.source}:{uid}"
