from __future__ import annotations
import argparse
import logging
import sys

from . import config as cfgmod
from .runner import Monitor


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tender-monitor", description="Pemantau pengumuman tender (LPSE + portal lain)")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="satu siklus: cek semua sumber & kirim notifikasi (untuk cron)")
    sub.add_parser("digest", help="kirim ringkasan harian")
    sub.add_parser("reminders", help="kirim pengingat batas pendaftaran (H-3, H-1)")
    sub.add_parser("loop", help="jalan terus dengan penjadwal bawaan (untuk Docker/server)")
    sub.add_parser("health", help="status tiap sumber")
    sub.add_parser("test-notify", help="kirim pesan uji ke semua kanal notifikasi")
    sub.add_parser("check", help="uji tiap sumber tanpa menyimpan/mengirim; tampilkan hasil mentah")
    ex = sub.add_parser("export", help="ekspor semua tender ke CSV")
    ex.add_argument("out", nargs="?", default="tender.csv")
    mk = sub.add_parser("mark", help="ubah status tender, mis. mark 'lpse-x/kemenkeu:12345' 'diproses'")
    mk.add_argument("key")
    mk.add_argument("status")
    a = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    m = Monitor(cfgmod.load(a.config))

    if a.cmd == "run":
        print(m.run_once())
    elif a.cmd == "digest":
        print(f"{m.send_digest()} item masuk ringkasan")
    elif a.cmd == "reminders":
        print(f"{m.send_reminders()} pengingat terkirim")
    elif a.cmd == "loop":
        m.loop()
    elif a.cmd == "health":
        for h in m.store.health():
            flag = "OK " if not h["failures"] else "ERR"
            print(f"[{flag}] {h['source']:<35} terakhir ok: {h['last_ok'] or '-':<26} item: {h['last_count']:<4} "
                  f"{('gagal ' + str(h['failures']) + 'x: ' + (h['last_error'] or '')) if h['failures'] else ''}")
    elif a.cmd == "test-notify":
        ok = m._broadcast("✅ Tes notifikasi tender-monitor berhasil.", "Tes notifikasi")
        return 0 if ok else 1
    elif a.cmd == "check":
        bad = 0
        for s in m.sources:
            try:
                items = s.fetch()
                print(f"[OK ] {s.name}: {len(items)} item")
                for t in items[:3]:
                    print(f"      - {t.title[:90]} | {t.agency[:40]} | batas={t.deadline or '-'} | {t.url}")
            except Exception as e:
                bad += 1
                print(f"[ERR] {s.name}: {type(e).__name__}: {e}")
        return 1 if bad else 0
    elif a.cmd == "export":
        print(f"{m.store.export_csv(a.out)} baris -> {a.out}")
    elif a.cmd == "mark":
        m.store.set_status(a.key, a.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
