from __future__ import annotations
import email
import imaplib
import re
from email.header import decode_header, make_header

from ..models import Tender
from ..utils import strip_html
from .base import Source


class ImapSource(Source):
    """Untuk portal yang hanya mengirim notifikasi vendor lewat email (atau butuh login/captcha).
    Daftarkan satu mailbox bersama ke portal-portal tersebut, lalu baca di sini.
    Config: host, user, password, folder (INBOX), from_contains: [..], max_messages, ssl (true)."""
    type = "imap"

    def fetch(self) -> list[Tender]:
        c = self.cfg
        M = imaplib.IMAP4_SSL(c["host"], c.get("port", 993)) if c.get("ssl", True) else imaplib.IMAP4(c["host"], c.get("port", 143))
        try:
            M.login(c["user"], c["password"])
            M.select(c.get("folder", "INBOX"), readonly=True)
            _, data = M.search(None, "ALL")
            ids = data[0].split()[-int(c.get("max_messages", 100)):]
            out = []
            for i in ids:
                _, msg = M.fetch(i, "(RFC822)")
                m = email.message_from_bytes(msg[0][1])
                sender = str(make_header(decode_header(m.get("From", ""))))
                if c.get("from_contains") and not any(s.lower() in sender.lower() for s in c["from_contains"]):
                    continue
                subject = str(make_header(decode_header(m.get("Subject", ""))))
                body = self._body(m)
                link = (re.findall(r"https?://[^\s<>\"']+", body) or [""])[0]
                out.append(Tender(source=self.name, uid=m.get("Message-ID", subject), title=subject, agency=sender,
                                  published=(m.get("Date") or "")[:16], url=link, extra={"summary": body[:2000]}))
            return out
        finally:
            try:
                M.logout()
            except Exception:
                pass

    @staticmethod
    def _body(m) -> str:
        parts = m.walk() if m.is_multipart() else [m]
        txt = ""
        for p in parts:
            if p.get_content_type() in ("text/plain", "text/html"):
                payload = p.get_payload(decode=True) or b""
                s = payload.decode(p.get_content_charset() or "utf-8", errors="replace")
                txt += strip_html(s) if p.get_content_type() == "text/html" else s
        return txt
