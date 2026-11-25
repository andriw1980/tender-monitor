from __future__ import annotations
import os
import re

import yaml

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand(v):
    if isinstance(v, str):
        return _ENV.sub(lambda m: os.environ.get(m[1], m[2] if m[2] is not None else ""), v)
    if isinstance(v, list):
        return [_expand(x) for x in v]
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    return v


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = _expand(yaml.safe_load(f) or {})
    cfg.setdefault("database", "tender.db")
    cfg.setdefault("keywords", {})
    cfg["keywords"].setdefault("include", [])
    cfg["keywords"].setdefault("exclude", [])
    cfg.setdefault("sources", [])
    cfg.setdefault("notifiers", [])
    s = cfg.setdefault("schedule", {})
    s.setdefault("interval_minutes", 60)
    s.setdefault("active_hours", "07-19")
    s.setdefault("digest_time", "08:00")
    s.setdefault("reminder_days", [3, 1])
    o = cfg.setdefault("options", {})
    o.setdefault("notify_on_first_run", False)
    o.setdefault("max_individual", 8)
    o.setdefault("alert_after_failures", 3)
    return cfg
