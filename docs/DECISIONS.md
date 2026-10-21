# Decision Log

Catat keputusan yang memengaruhi validitas, ruang lingkup, atau kemampuan
reproduksi benchmark. Jangan gunakan dokumen ini untuk log aktivitas rutin.

| Tanggal | ID | Keputusan | Alasan/Bukti | Dampak | Pemilik |
| --- | --- | --- | --- | --- | --- |
| 2026-10-05 | D-001 | Menggunakan Python 3.12 dan MLX lokal yang telah tervalidasi berjalan. | Instalasi awal berhasil; versi akan dicatat di manifest. | Baseline environment proyek. | Tim |
| 2026-10-21 | D-002 | *Proposed:* sampling `powermetrics` 100 ms, daya run diintegrasikan berbobot waktu pada jendela run, run dengan cakupan < 0,9 = `incomplete`. | Run model 0.6B/256 token ±1–2 s hanya mendapat 2–4 sampel pada 500 ms. | J/token lebih stabil; overhead `powermetrics` naik sedikit. Perlu verifikasi di Mac target (T04). | A, review B |
| 2026-10-21 | D-003 | *Proposed:* `duration_s` = jendela end-to-end `stream_generate` termasuk prefill; idle diukur ulang tiap 10 run; nilai negatif dipotong dan ditandai `energy_clipped`. | Definisi sebelumnya ambigu; idle sekali per blok tidak menangkap drift thermal. | Skema bertambah field `energy_clipped`, `power_*`, `output_sha256`, parameter decoding. | A, review B |
| 2026-10-21 | D-004 | *Proposed:* bila Qwen3-4B bf16 `skipped_resource_limit`, target bf16 Eksperimen B diganti 4B 8-bit dengan experiment ID baru. | Eksperimen B mewajibkan 4B bf16, sedangkan Eksperimen A hanya "jika feasible". | Eksperimen B tetap punya dua target precision. | Tim |
| 2026-10-21 | D-005 | *Open:* tenggat awal 5–9 Oktober 2026 sudah lewat tanpa implementasi; jadwal baru perlu dikonfirmasi pengajar. | Tanggal hari ini 21 Oktober 2026. | Menentukan apakah fitur P1 tetap dikerjakan. | Tim/pengajar |

## Template keputusan

```markdown
### D-XXX — Judul singkat

- Tanggal:
- Status: proposed / accepted / superseded
- Keputusan:
- Alternatif yang dipertimbangkan:
- Bukti/alasan:
- Dampak terhadap data atau jadwal:
```
