from __future__ import annotations
import logging
import time
from datetime import datetime, timedelta
from html import escape

from . import config as cfgmod
from .filters import match_keywords
from .formatting import tender_html
from .notifiers import build_notifiers
from .sources import build_sources
from .storage import Store
from .utils import today

log = logging.getLogger("tender-monitor")


class Monitor:
    def __init__(self, cfg: dict, store: Store | None = None, sources=None, notifiers=None):
        self.cfg = cfg
        self.store = store or Store(cfg["database"])
        self.sources = sources if sources is not None else build_sources(cfg["sources"])
        self.notifiers = notifiers if notifiers is not None else build_notifiers(cfg["notifiers"])
        self.opt = cfg["options"]

    # ---------- kirim ----------
    def _broadcast(self, html: str, subject: str) -> bool:
        ok = False
        for n in self.notifiers:
            try:
                n.send(html, subject)
                ok = True
            except Exception as e:
                log.error("notifikasi %s gagal: %s", n.name, e)
        return ok

    # ---------- siklus utama ----------
    def run_once(self) -> dict:
        kw = self.cfg["keywords"]
        stats = {"sources": 0, "failed": 0, "seen": 0, "new": 0}
        for src in self.sources:
            stats["sources"] += 1
            first_run = not any(h["source"] == src.name and h["last_ok"] for h in self.store.health())
            try:
                items = src.fetch()
            except Exception as e:
                stats["failed"] += 1
                n = self.store.health_fail(src.name, f"{type(e).__name__}: {e}")
                log.warning("sumber %s gagal (%dx): %s", src.name, n, e)
                if n >= self.opt["alert_after_failures"] and self.store.should_alert(src.name):
                    if self._broadcast(f"⚠️ <b>Sumber tender bermasalah</b>\n{escape(src.name)} gagal {n}x berturut-turut.\n"
                                       f"<code>{escape(str(e)[:300])}</code>\nPengumuman dari sumber ini mungkin terlewat — "
                                       f"cek manual & perbaiki adapter.", "Sumber tender bermasalah"):
                        self.store.mark_alerted(src.name)
                continue
            self.store.health_ok(src.name, len(items))
            stats["seen"] += len(items)
            silent = first_run and not self.opt["notify_on_first_run"]
            for t in items:
                text = f"{t.title} {t.agency} {t.extra.get('summary', '')}"
                hits = match_keywords(text, kw["include"] if src.use_filter else [], kw["exclude"])
                if hits is None or not self.store.is_new(t):
                    continue
                self.store.add(t, hits, notified=silent)
                if not silent:
                    stats["new"] += 1
            if silent:
                log.info("%s: run pertama, %d item dicatat tanpa notifikasi (baseline)", src.name, len(items))
        self.flush_pending()
        return stats

    def flush_pending(self) -> int:
        rows = self.store.pending()
        if not rows:
            return 0
        if len(rows) > self.opt["max_individual"]:
            body = [f"🆕 <b>{len(rows)} pengumuman tender baru</b>\n"]
            for r in rows:
                body.append(f"• <b>{escape(r['title'])}</b>\n  {escape(r['agency'] or r['source'])}"
                            + (f" · ⏰ {r['deadline']}" if r["deadline"] else "")
                            + (f"\n  <a href=\"{escape(r['url'], quote=True)}\">buka</a>" if r["url"] else ""))
            sent = self._broadcast("\n".join(body), f"{len(rows)} tender baru")
        else:
            sent = True
            for r in rows:
                if not self._broadcast(tender_html(r), "Tender baru: " + r["title"][:80]):
                    sent = False
                    break
        if sent:
            for r in rows:
                self.store.mark_notified(r["key"])
            return len(rows)
        log.error("semua kanal notifikasi gagal; %d item akan dicoba lagi pada siklus berikutnya", len(rows))
        return 0

    # ---------- ringkasan harian & pengingat ----------
    def send_digest(self) -> int:
        rows = self.store.undigested()
        closing = self.store.closing_between(today(), (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        health = [h for h in self.store.health() if h["failures"]]
        if not rows and not closing and not health:
            return 0
        parts = [f"📋 <b>Ringkasan tender — {datetime.now():%d %b %Y}</b>"]
        if rows:
            parts.append(f"\n<b>Baru sejak ringkasan terakhir ({len(rows)})</b>")
            cur = None
            for r in rows:
                if r["source"] != cur:
                    cur = r["source"]
                    parts.append(f"\n<i>{escape(cur)}</i>")
                parts.append(f"• {escape(r['title'])}" + (f" ({escape(r['agency'])})" if r["agency"] else ""))
        if closing:
            parts.append("\n<b>⏰ Batas pendaftaran ≤ 7 hari</b>")
            parts += [f"• {r['deadline']} — {escape(r['title'])}" for r in closing]
        if health:
            parts.append("\n<b>⚠️ Sumber bermasalah</b>")
            parts += [f"• {escape(h['source'])}: {h['failures']}x gagal — {escape(h['last_error'] or '')[:120]}" for h in health]
        if self._broadcast("\n".join(parts), "Ringkasan tender harian"):
            self.store.mark_digested([r["key"] for r in rows])
        return len(rows)

    def send_reminders(self) -> int:
        n = 0
        for d in self.cfg["schedule"]["reminder_days"]:
            target = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
            for r in self.store.closing_between(target, target):
                kind = f"H-{d}"
                if r["status"] in ("tidak ikut", "selesai") or self.store.reminder_sent(r["key"], kind):
                    continue
                if self._broadcast(f"⏰ <b>Pengingat {kind}</b> — batas pendaftaran {r['deadline']}\n" + tender_html(r),
                                   f"Pengingat {kind}: {r['title'][:60]}"):
                    self.store.mark_reminder(r["key"], kind)
                    n += 1
        return n

    # ---------- penjadwal bawaan (tanpa cron) ----------
    def loop(self) -> None:  # pragma: no cover - loop tak berujung
        s = self.cfg["schedule"]
        a, b = (int(x) for x in str(s["active_hours"]).split("-"))
        last_digest = None
        log.info("loop dimulai: tiap %s menit, jam aktif %02d-%02d, ringkasan %s", s["interval_minutes"], a, b, s["digest_time"])
        while True:
            now = datetime.now()
            if a <= now.hour < b:
                try:
                    log.info("siklus: %s", self.run_once())
                    self.send_reminders()
                except Exception:
                    log.exception("siklus gagal")
            if now.strftime("%H:%M") >= s["digest_time"] and last_digest != now.date():
                try:
                    self.send_digest()
                    last_digest = now.date()
                except Exception:
                    log.exception("ringkasan gagal")
            time.sleep(int(s["interval_minutes"]) * 60)
