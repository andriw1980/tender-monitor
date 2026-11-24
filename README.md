# Tender Monitor

Pemantau pengumuman tender otomatis untuk tim admin support: mengumpulkan pengumuman dari **LPSE (SPSE/INAPROC)**, portal e-procurement perusahaan (RSS / scraping HTML / email notifikasi vendor), menyaringnya dengan kata kunci, lalu mengirim notifikasi (Telegram, email, webhook).

## Fitur
- **Sumber**: `lpse` (via library `pyproc`), `rss`, `html` (CSS selector, tanpa coding), `imap` (notifikasi vendor via email)
- **Dedup** (SQLite): satu pengumuman hanya dikirim sekali
- **Filter kata kunci** include/exclude, bisa dimatikan per sumber (`filter: false`)
- **Notifikasi**: Telegram, email SMTP, webhook (n8n/Teams/Slack/WhatsApp gateway), console
- **Ringkasan harian** + **pengingat H-3 / H-1** sebelum batas pendaftaran
- **Pemantauan kesehatan sumber**: bila portal gagal/berubah struktur, tim diberi tahu (bukan diam-diam "tidak ada tender")
- **Baseline run pertama**: tidak membanjiri notifikasi dengan data lama
- **Retry notifikasi**: bila Telegram sedang down, pesan dikirim ulang di siklus berikutnya
- Ekspor CSV, penandaan status (`diproses`, `tidak ikut`, ...)

## Mulai cepat
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml      # lalu edit: kata kunci, sumber, notifikasi
cp .env.example .env && export $(grep -v '^#' .env | xargs)   # token Telegram dsb.

python -m tender_monitor check          # uji tiap sumber (tidak menyimpan/mengirim apa pun)
python -m tender_monitor test-notify    # uji kanal notifikasi
python -m tender_monitor run            # satu siklus penuh
```

### Menjalankan terus-menerus
**Docker (disarankan, di server/VM kantor):**
```bash
docker compose up -d --build
docker compose logs -f
```
Penjadwal bawaan (`loop`) mengecek tiap `interval_minutes` pada `active_hours`, mengirim ringkasan pada `digest_time`, dan pengingat deadline.

**Atau cron** (tanpa Docker):
```
0 7-18 * * 1-6  cd /opt/tender-monitor && .venv/bin/python -m tender_monitor run
0 8    * * 1-6  cd /opt/tender-monitor && .venv/bin/python -m tender_monitor digest
5 8    * * 1-6  cd /opt/tender-monitor && .venv/bin/python -m tender_monitor reminders
```

## Menambah portal baru
1. Cek apakah portal punya **RSS** → pakai `type: rss` (paling stabil).
2. Jika tidak, pakai `type: html`: buka halaman daftar pengumuman, Inspect satu baris, isi `item` dan `fields`. Uji dengan `check`.
3. Jika portal butuh **login/captcha**: daftarkan mailbox bersama sebagai akun vendor, aktifkan notifikasi email, pakai `type: imap`.
4. Portal yang halamannya dirender JavaScript (daftar kosong pada `check`) butuh adapter khusus (mis. Playwright) atau cari endpoint JSON-nya di tab Network browser.

Menambah **LPSE**: cukup tambahkan kodenya di `hosts` (bagian setelah `spse.inaproc.id/`).

## Perintah
| Perintah | Fungsi |
|---|---|
| `run` | satu siklus cek + notifikasi |
| `loop` | jalan terus dengan penjadwal bawaan |
| `digest` / `reminders` | ringkasan harian / pengingat deadline |
| `check` | uji sumber tanpa efek samping |
| `health` | status tiap sumber |
| `export [file.csv]` | ekspor semua tender |
| `mark <key> <status>` | ubah status tender |
| `test-notify` | uji kanal notifikasi |

## Catatan penting
- **LPSE**: adapter memakai `pyproc`, yang membaca endpoint DataTables SPSE. Struktur kolom bisa berbeda antarversi SPSE, dan **SPSE v.5 INAPROC** sedang disiapkan LKPP — bila `check` mulai gagal setelah migrasi, adapter ini yang perlu disesuaikan.
- Hormati syarat penggunaan tiap portal; jangan menurunkan `interval_minutes` terlalu agresif.
- Simpan kredensial hanya di `.env` / environment, jangan di `config.yaml` yang dibagikan.
- Jangan abaikan peringatan "Sumber tender bermasalah" — itu tanda ada pengumuman yang mungkin terlewat.

## Uji
```bash
pytest -q      # 12 tes offline (filter, dedup, baseline, retry, alert sumber, adapter HTML/LPSE, config)
```

## Struktur
```
tender_monitor/
  sources/   lpse.py rss.py html.py imap.py   <- tambah adapter baru di sini
  notifiers/ telegram, email, webhook, console
  runner.py  siklus, ringkasan, pengingat, loop
  storage.py SQLite (dedup, status, kesehatan sumber)
  filters.py kata kunci
config.example.yaml
```
