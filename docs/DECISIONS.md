# Decision Log

Catat keputusan yang memengaruhi validitas, ruang lingkup, atau kemampuan
reproduksi benchmark. Jangan gunakan dokumen ini untuk log aktivitas rutin.

| Tanggal | ID | Keputusan | Alasan/Bukti | Dampak | Pemilik |
| --- | --- | --- | --- | --- | --- |
| 2026-10-05 | D-001 | Menggunakan Python 3.12 dan MLX lokal yang telah tervalidasi berjalan. | Instalasi awal berhasil; versi akan dicatat di manifest. | Baseline environment proyek. | Tim |
| 2026-10-21 | D-002 | *Accepted (2026-10-25):* sampling `powermetrics` 100 ms, daya run diintegrasikan berbobot waktu pada jendela run, run dengan cakupan < 0,9 = `incomplete`. | Run model 0.6B/256 token ±1–2 s hanya mendapat 2–4 sampel pada 500 ms. | J/token lebih stabil; overhead `powermetrics` naik sedikit. Perlu verifikasi di Mac target (T04). | A |
| 2026-10-21 | D-003 | *Accepted (2026-10-25):* `duration_s` = jendela end-to-end `stream_generate` termasuk prefill; idle diukur ulang tiap 10 run; nilai negatif dipotong dan ditandai `energy_clipped`. | Definisi sebelumnya ambigu; idle sekali per blok tidak menangkap drift thermal. | Skema bertambah field `energy_clipped`, `power_*`, `output_sha256`, parameter decoding. | A |
| 2026-10-21 | D-004 | *Accepted (2026-10-25):* bila Qwen3-4B bf16 `skipped_resource_limit`, target bf16 Eksperimen B diganti 4B 8-bit dengan experiment ID baru. | Eksperimen B mewajibkan 4B bf16, sedangkan Eksperimen A hanya "jika feasible". | Eksperimen B tetap punya dua target precision. | A |
| 2026-10-21 | D-005 | *Open:* tenggat awal 5–9 Oktober 2026 sudah lewat tanpa implementasi; jadwal baru perlu dikonfirmasi pengajar. | Tanggal hari ini 21 Oktober 2026. | Menentukan apakah fitur P1 tetap dikerjakan. | Tim/pengajar |
| 2026-10-24 | D-006 | *Accepted (2026-10-25):* Eksperimen B menjalankan baseline tanpa draft sendiri (`B-speculative`), dan semua model di-pin ke commit Hugging Face di `config/defaults.yaml`. | Baseline dari sesi lain (Eksperimen A) bisa berbeda kondisi thermal/latar; repo model dapat diperbarui setelah validasi. | +60 record di B; `load()` memakai `revision` sehingga bobot model sama di setiap run. | A |
| 2026-10-24 | D-007 | *Accepted:* anggota A juga mengerjakan seluruh peran B (NOTES, prompt, config, validasi, agregasi, grafik). *Accepted (2026-10-25):* pengganti review silang = PR ke `main`, CI hijau, dan checklist self-review di TEAM_WORKFLOW. Pada 2026-10-25 pemilik mendelegasikan pengerjaan dan keputusan teknis ke asisten (Claude Code) tanpa persetujuan per langkah; D-002–D-004, D-006, dan D-008 diterima atas dasar delegasi itu dan dapat dibuka ulang pemilik kapan saja. | Keputusan pemilik proyek pada 2026-10-24. | Review antar-anggota tidak tersedia; keputusan yang sebelumnya menunggu "review B" (D-002–D-004, D-006) kini diputuskan oleh A. | A |
| 2026-10-25 | D-008 | *Accepted:* pin `mlx==0.32.3` dan `mlx-lm==0.32.1` (rilis PyPI) di `requirements.txt`, menggantikan build dev `0.32.1.dev6`. | Build dev tidak bisa dipasang ulang dari PyPI; 0.32.1 adalah versi yang diperiksa di NOTES dan lolos smoke run. | Lingkungan bisa direproduksi dari README; Mac target perlu `pip install -r requirements.txt` ulang sebelum data dikumpulkan. | A |

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
