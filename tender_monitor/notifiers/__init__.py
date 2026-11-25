from __future__ import annotations
import smtplib
from email.mime.text import MIMEText

import requests

from ..formatting import strip_tags


class Notifier:
    name = "base"

    def send(self, html: str, subject: str = "") -> None:  # pragma: no cover
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    name = "console"

    def __init__(self, cfg: dict):
        pass

    def send(self, html: str, subject: str = "") -> None:
        print(f"\n--- {subject or 'notifikasi'} ---\n{strip_tags(html)}\n")


class TelegramNotifier(Notifier):
    """Config: bot_token, chat_id (grup atau personal; untuk topik forum tambahkan thread_id)."""
    name = "telegram"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def send(self, html: str, subject: str = "") -> None:
        for chunk in _split(html, 3800):
            payload = {"chat_id": self.cfg["chat_id"], "text": chunk, "parse_mode": "HTML",
                       "disable_web_page_preview": True}
            if self.cfg.get("thread_id"):
                payload["message_thread_id"] = self.cfg["thread_id"]
            r = requests.post(f"https://api.telegram.org/bot{self.cfg['bot_token']}/sendMessage", json=payload, timeout=20)
            if r.status_code >= 400:
                raise RuntimeError(f"Telegram {r.status_code}: {r.text[:200]}")


class EmailNotifier(Notifier):
    """Config: host, port, user, password, from, to: [..], starttls (true)."""
    name = "email"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def send(self, html: str, subject: str = "") -> None:
        c = self.cfg
        msg = MIMEText(html.replace("\n", "<br>\n"), "html", "utf-8")
        msg["Subject"] = subject or "Notifikasi tender"
        msg["From"] = c.get("from", c["user"])
        msg["To"] = ", ".join(c["to"])
        with smtplib.SMTP(c["host"], int(c.get("port", 587)), timeout=30) as s:
            if c.get("starttls", True):
                s.starttls()
            s.login(c["user"], c["password"])
            s.sendmail(msg["From"], c["to"], msg.as_string())


class WebhookNotifier(Notifier):
    """POST JSON {"subject","text","html"} ke URL. Cocok untuk n8n, Teams/Slack (incoming webhook),
    atau gateway WhatsApp yang Anda punya. Config: url, headers (opsional)."""
    name = "webhook"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def send(self, html: str, subject: str = "") -> None:
        r = requests.post(self.cfg["url"], json={"subject": subject, "text": strip_tags(html), "html": html},
                          headers=self.cfg.get("headers", {}), timeout=20)
        if r.status_code >= 400:
            raise RuntimeError(f"Webhook {r.status_code}: {r.text[:200]}")


def _split(text: str, n: int):
    while text:
        if len(text) <= n:
            yield text
            return
        cut = text.rfind("\n\n", 0, n)
        cut = cut if cut > 0 else n
        yield text[:cut]
        text = text[cut:].lstrip()


BUILDERS = {"console": ConsoleNotifier, "telegram": TelegramNotifier, "email": EmailNotifier, "webhook": WebhookNotifier}


def build_notifiers(entries: list[dict]) -> list[Notifier]:
    out = []
    for e in entries or []:
        if e.get("enabled", True) is False:
            continue
        e = dict(e)
        typ = e.pop("type")
        if typ not in BUILDERS:
            raise ValueError(f"tipe notifikasi tidak dikenal: {typ}")
        out.append(BUILDERS[typ](e))
    return out or [ConsoleNotifier({})]
