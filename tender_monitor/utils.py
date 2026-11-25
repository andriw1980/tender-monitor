from __future__ import annotations
import re
from datetime import datetime
from html import unescape

_BULAN = {"januari": 1, "jan": 1, "februari": 2, "feb": 2, "pebruari": 2, "maret": 3, "mar": 3, "april": 4, "apr": 4,
          "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "agustus": 8, "agu": 8, "agt": 8, "aug": 8,
          "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11,
          "nop": 11, "desember": 12, "des": 12, "dec": 12}


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", unescape(s)).strip()


def parse_date(text: str) -> str:
    """Ubah teks tanggal (Indonesia/Inggris/ISO) ke YYYY-MM-DD. Kosong bila gagal."""
    if not text:
        return ""
    t = strip_html(text).lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
    if m:
        return f"{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.search(r"(\d{1,2})\s+([a-z]+)\.?,?\s+(\d{4})", t)
    if m and m[2] in _BULAN:
        return f"{int(m[3]):04d}-{_BULAN[m[2]]:02d}-{int(m[1]):02d}"
    m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and m[1] in _BULAN:
        return f"{int(m[3]):04d}-{_BULAN[m[1]]:02d}-{int(m[2]):02d}"
    return ""


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")
