from __future__ import annotations
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import Tender
from ..utils import parse_date, strip_html
from .base import Source


class HtmlSource(Source):
    """Scraper generik berbasis CSS selector, untuk portal tanpa RSS/API.

    Config:
      url, item (selector tiap baris/kartu pengumuman),
      fields: {title, link, agency, published, deadline, budget, uid}  -> tiap isinya selector CSS
              (opsional "selector@atribut", mis. "a@href"; link otomatis diambil dari atribut href)
      pages: daftar URL tambahan (paginasi), verify_ssl, headers
    """
    type = "html"

    def fetch(self) -> list[Tender]:
        urls = [self.cfg["url"], *self.cfg.get("pages", [])]
        out: list[Tender] = []
        for u in urls:
            r = requests.get(u, timeout=int(self.cfg.get("timeout", 30)), verify=self.cfg.get("verify_ssl", True),
                             headers={"User-Agent": "Mozilla/5.0 (compatible; tender-monitor/0.1)",
                                      **self.cfg.get("headers", {})})
            r.raise_for_status()
            out += self.parse(r.text, u)
        return out

    def parse(self, html: str, page_url: str) -> list[Tender]:
        soup = BeautifulSoup(html, "html.parser")
        f = self.cfg["fields"]
        items = soup.select(self.cfg["item"])
        if not items:
            raise RuntimeError(f"selector item '{self.cfg['item']}' tidak menemukan apa pun - struktur halaman mungkin berubah")
        res = []
        for it in items:
            title = self._get(it, f.get("title"))
            if not title:
                continue
            link = self._get(it, f.get("link", f.get("title")), attr="href")
            link = urljoin(self.cfg.get("base_url", page_url), link) if link else page_url
            uid = self._get(it, f.get("uid")) if f.get("uid") else link
            res.append(Tender(source=self.name, uid=uid or link, title=title,
                              agency=self._get(it, f.get("agency")) or self.cfg.get("agency", ""),
                              budget=self._get(it, f.get("budget")),
                              published=parse_date(self._get(it, f.get("published"))),
                              deadline=parse_date(self._get(it, f.get("deadline"))), url=link))
        return res

    @staticmethod
    def _get(node, spec: str | None, attr: str | None = None) -> str:
        if not spec:
            return ""
        sel, _, a = spec.partition("@")
        a = a or attr
        el = node.select_one(sel) if sel else node
        if el is None:
            return ""
        if a and el.has_attr(a):
            return str(el[a]).strip()
        if attr and not a:
            return ""
        return strip_html(el.get_text(" "))
