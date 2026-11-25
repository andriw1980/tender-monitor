import pytest

from tender_monitor.filters import match_keywords
from tender_monitor.models import Tender
from tender_monitor.runner import Monitor
from tender_monitor.sources import build_sources
from tender_monitor.sources.html import HtmlSource
from tender_monitor.sources.lpse import LpseSource
from tender_monitor.sources.base import Source
from tender_monitor.storage import Store
from tender_monitor.utils import parse_date
from tender_monitor import config as cfgmod


class Fake(Source):
    def __init__(self, name, items=None, fail=None, **kw):
        super().__init__(name, kw)
        self.items, self.fail = items or [], fail

    def fetch(self):
        if self.fail:
            raise RuntimeError(self.fail)
        return self.items


class Sink:
    name = "sink"

    def __init__(self, ok=True):
        self.msgs, self.ok = [], ok

    def send(self, html, subject=""):
        if not self.ok:
            raise RuntimeError("down")
        self.msgs.append((subject, html))


def cfg(**o):
    c = {"database": ":memory:", "keywords": {"include": ["aplikasi", "sistem informasi"], "exclude": ["konstruksi"]},
         "sources": [], "notifiers": [], "schedule": {"reminder_days": [3, 1]},
         "options": {"notify_on_first_run": True, "max_individual": 3, "alert_after_failures": 2}}
    c["options"].update(o)
    return c


def T(i, title, **k):
    return Tender(source="s", uid=str(i), title=title, **k)


def test_keywords():
    assert match_keywords("Pengembangan Aplikasi Mobile", ["aplikasi"], []) == ["aplikasi"]
    assert match_keywords("Pembangunan gedung", ["aplikasi"], []) is None
    assert match_keywords("Aplikasi konstruksi", ["aplikasi"], ["konstruksi"]) is None
    assert match_keywords("apa saja", [], []) == []
    assert match_keywords("Sistem  Informasi\nPajak", ["sistem informasi"]) == ["sistem informasi"]


def test_dates():
    assert parse_date("Batas: 5 November 2026") == "2026-11-05"
    assert parse_date("05/11/2026") == "2026-11-05"
    assert parse_date("2026-11-05 10:00") == "2026-11-05"
    assert parse_date("Nov 5, 2026") == "2026-11-05"
    assert parse_date("-") == ""


def test_dedup_and_notify():
    sink = Sink()
    m = Monitor(cfg(), Store(":memory:"), [Fake("a", [T(1, "Aplikasi A"), T(2, "Gedung B")])], [sink])
    assert m.run_once()["new"] == 1
    assert len(sink.msgs) == 1
    m.run_once()
    assert len(sink.msgs) == 1          # tidak dobel


def test_first_run_baseline_silent():
    sink = Sink()
    m = Monitor(cfg(notify_on_first_run=False), Store(":memory:"), [Fake("a", [T(1, "Aplikasi A")])], [sink])
    m.run_once()
    assert sink.msgs == []
    m.sources[0].items = [T(1, "Aplikasi A"), T(2, "Aplikasi Baru")]
    m.run_once()
    assert len(sink.msgs) == 1 and "Aplikasi Baru" in sink.msgs[0][1]


def test_grouped_when_many():
    sink = Sink()
    items = [T(i, f"Aplikasi {i}") for i in range(5)]
    Monitor(cfg(), Store(":memory:"), [Fake("a", items)], [sink]).run_once()
    assert len(sink.msgs) == 1 and "5 pengumuman" in sink.msgs[0][1]


def test_retry_when_notifier_down():
    bad, st = Sink(ok=False), Store(":memory:")
    m = Monitor(cfg(), st, [Fake("a", [T(1, "Aplikasi A")])], [bad])
    m.run_once()
    assert len(st.pending()) == 1
    good = Sink()
    m.notifiers = [good]
    m.run_once()
    assert len(good.msgs) == 1 and not st.pending()


def test_source_failure_alert_once():
    sink = Sink()
    m = Monitor(cfg(), Store(":memory:"), [Fake("a", fail="timeout"), Fake("b", [T(1, "Aplikasi")])], [sink])
    m.run_once()
    assert len(sink.msgs) == 1           # hanya b; 'a' baru gagal 1x
    m.run_once()
    alerts = [s for s in sink.msgs if "bermasalah" in s[0]]
    assert len(alerts) == 1
    m.run_once()
    assert len([s for s in sink.msgs if "bermasalah" in s[0]]) == 1   # tidak spam


def test_unfiltered_source():
    sink = Sink()
    Monitor(cfg(), Store(":memory:"), [Fake("a", [T(1, "Pengadaan Kursi")], filter=False)], [sink]).run_once()
    assert len(sink.msgs) == 1


def test_reminders_and_digest():
    from datetime import datetime, timedelta
    d3 = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    sink = Sink()
    m = Monitor(cfg(), Store(":memory:"), [Fake("a", [T(1, "Aplikasi A", deadline=d3)])], [sink])
    m.run_once()
    assert m.send_reminders() == 1 and m.send_reminders() == 0
    assert m.send_digest() == 1


HTML = """<div class=row><a class=t href="/p/1">Pengadaan Aplikasi X</a><span class=ag>PT Maju</span>
<span class=dl>Batas: 12 Desember 2026</span></div><div class=row><a class=t href="/p/2">Kursi</a></div>"""


def test_html_adapter():
    s = HtmlSource("p", {"url": "https://x.id/list", "item": ".row",
                         "fields": {"title": "a.t", "agency": ".ag", "deadline": ".dl"}})
    r = s.parse(HTML, "https://x.id/list")
    assert r[0].url == "https://x.id/p/1" and r[0].deadline == "2026-12-12" and r[0].agency == "PT Maju"
    s.cfg["item"] = ".gone"
    with pytest.raises(RuntimeError):
        s.parse(HTML, "https://x.id/list")


def test_lpse_row_and_build():
    s = LpseSource("lpse/x", {"host": "x"})
    t = s._row(["123", "Pengadaan <b>Aplikasi</b>", "Dinas A", "Pengumuman", "Rp 1 M"], "https://spse.inaproc.id/x", "lelang")
    assert t.title == "Pengadaan Aplikasi" and t.url.endswith("/lelang/123/pengumumanlelang")
    srcs = build_sources([{"type": "lpse", "name": "lpse", "hosts": ["a", "b"]}, {"type": "rss", "name": "r", "url": "u", "enabled": False}])
    assert [x.name for x in srcs] == ["lpse/a", "lpse/b"]


def test_config_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TOK", "abc")
    p = tmp_path / "c.yaml"
    p.write_text("notifiers:\n  - {type: telegram, bot_token: '${TOK}', chat_id: '${NOPE:-42}'}\n")
    c = cfgmod.load(str(p))
    assert c["notifiers"][0]["bot_token"] == "abc" and c["notifiers"][0]["chat_id"] == "42"
    assert c["schedule"]["interval_minutes"] == 60
