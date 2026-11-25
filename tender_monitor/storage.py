from __future__ import annotations
import csv
import json
import sqlite3
from datetime import datetime, timezone

from .models import Tender

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenders(
  key TEXT PRIMARY KEY, source TEXT, uid TEXT, title TEXT, agency TEXT, budget TEXT,
  published TEXT, deadline TEXT, stage TEXT, url TEXT, extra TEXT,
  keywords TEXT, first_seen TEXT, notified INTEGER DEFAULT 0, in_digest INTEGER DEFAULT 0,
  status TEXT DEFAULT 'baru'
);
CREATE TABLE IF NOT EXISTS reminders(key TEXT, kind TEXT, PRIMARY KEY(key, kind));
CREATE TABLE IF NOT EXISTS source_health(
  source TEXT PRIMARY KEY, last_run TEXT, last_ok TEXT, last_count INTEGER DEFAULT 0,
  failures INTEGER DEFAULT 0, last_error TEXT, alerted INTEGER DEFAULT 0
);
"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- tender ----
    def is_new(self, t: Tender) -> bool:
        return self.db.execute("SELECT 1 FROM tenders WHERE key=?", (t.key,)).fetchone() is None

    def add(self, t: Tender, keywords: list[str], notified: bool = False) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO tenders(key,source,uid,title,agency,budget,published,deadline,stage,url,extra,"
            "keywords,first_seen,notified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (t.key, t.source, t.uid, t.title, t.agency, t.budget, t.published, t.deadline, t.stage, t.url,
             json.dumps(t.extra, ensure_ascii=False), ", ".join(keywords), now(), int(notified)))
        self.db.commit()

    def mark_notified(self, key: str) -> None:
        self.db.execute("UPDATE tenders SET notified=1 WHERE key=?", (key,))
        self.db.commit()

    def pending(self) -> list[sqlite3.Row]:
        """Tender yang sudah tersimpan tapi notifikasinya belum terkirim (mis. Telegram sempat gagal)."""
        return self.db.execute("SELECT * FROM tenders WHERE notified=0 ORDER BY first_seen").fetchall()

    def since(self, iso: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM tenders WHERE first_seen>=? ORDER BY source, first_seen", (iso,)).fetchall()

    def undigested(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM tenders WHERE in_digest=0 ORDER BY source, first_seen").fetchall()

    def mark_digested(self, keys: list[str]) -> None:
        self.db.executemany("UPDATE tenders SET in_digest=1 WHERE key=?", [(k,) for k in keys])
        self.db.commit()

    def closing_between(self, d_from: str, d_to: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM tenders WHERE deadline!='' AND deadline>=? AND deadline<=? ORDER BY deadline",
            (d_from, d_to)).fetchall()

    def reminder_sent(self, key: str, kind: str) -> bool:
        return self.db.execute("SELECT 1 FROM reminders WHERE key=? AND kind=?", (key, kind)).fetchone() is not None

    def mark_reminder(self, key: str, kind: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO reminders VALUES(?,?)", (key, kind))
        self.db.commit()

    def set_status(self, key: str, status: str) -> None:
        self.db.execute("UPDATE tenders SET status=? WHERE key=?", (status, key))
        self.db.commit()

    # ---- kesehatan sumber ----
    def health_ok(self, source: str, count: int) -> None:
        self.db.execute(
            "INSERT INTO source_health(source,last_run,last_ok,last_count,failures,last_error,alerted) VALUES(?,?,?,?,0,'',0) "
            "ON CONFLICT(source) DO UPDATE SET last_run=excluded.last_run,last_ok=excluded.last_ok,"
            "last_count=excluded.last_count,failures=0,last_error='',alerted=0",
            (source, now(), now(), count))
        self.db.commit()

    def health_fail(self, source: str, err: str) -> int:
        self.db.execute(
            "INSERT INTO source_health(source,last_run,failures,last_error) VALUES(?,?,1,?) "
            "ON CONFLICT(source) DO UPDATE SET last_run=excluded.last_run,failures=failures+1,last_error=excluded.last_error",
            (source, now(), err[:500]))
        self.db.commit()
        return self.db.execute("SELECT failures FROM source_health WHERE source=?", (source,)).fetchone()[0]

    def health(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM source_health ORDER BY source").fetchall()

    def should_alert(self, source: str) -> bool:
        r = self.db.execute("SELECT alerted FROM source_health WHERE source=?", (source,)).fetchone()
        return bool(r) and not r["alerted"]

    def mark_alerted(self, source: str) -> None:
        self.db.execute("UPDATE source_health SET alerted=1 WHERE source=?", (source,))
        self.db.commit()

    def export_csv(self, path: str) -> int:
        rows = self.db.execute("SELECT first_seen,status,source,title,agency,budget,published,deadline,stage,keywords,url "
                               "FROM tenders ORDER BY first_seen DESC").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["ditemukan", "status", "sumber", "judul", "instansi", "pagu/HPS", "tayang", "batas", "tahap",
                        "kata_kunci", "url"])
            for r in rows:
                w.writerow(list(r))
        return len(rows)
