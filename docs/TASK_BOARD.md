# Task Board — Project 4

Status yang dipakai: `TODO`, `IN PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`.
Pemilik awal adalah usulan; tim dapat menukarnya saat stand-up. Sejak
2026-10-24 semua tugas B dikerjakan anggota A (D-007); kolom pemilik mencatat
peran asal agar riwayat tetap terbaca.

| ID | Pekerjaan | Pemilik | Dependensi | Status | Definition of Done |
| --- | --- | --- | --- | --- | --- |
| T01 | Catat manifest mesin dan package | A | — | TODO | `data/manifests/environment.md` berisi chip, RAM, macOS, Python, MLX/MLX-LM, disk. |
| T02 | Validasi model ID dan kapasitas disk/RAM | A | T01 | IN PROGRESS | Semua ID model di config nyata atau diberi status unavailable. 9 ID tervalidasi di Hugging Face dan di-pin (±23 GB unduhan); tinggal cek disk/RAM di Mac target. |
| T03 | Reverse engineer `generate.py` | B → A | akses clone MLX | DONE | Empat pertanyaan di `docs/NOTES.md` terjawab untuk versi source yang tepat. Terjawab untuk `mlx-lm` 0.32.1, versi yang di-pin di `requirements.txt` (D-008) dan diverifikasi dengan smoke run CPU. |
| T04 | Uji output dan hak akses `powermetrics` | A | T01 | IN PROGRESS | Contoh output dan parser test tersedia. Parser + test dengan fixture sintetis sudah ada; tinggal output asli dari Mac target. |
| T05 | Tetapkan prompt canonical dan provenance | B → A | — | DONE | `prompts/gsm8k_10.jsonl` dan README prompt selesai. |
| T06 | Definisikan config eksperimen A/B | B → A | T02, T03 | DONE | File YAML menyebut semua parameter dan model ID. D-006 diterima. |
| T07 | Implementasi bench runner | A | T03, T04, T05 | IN PROGRESS | Smoke run membuat JSONL valid. Smoke run CPU tanpa daya (baseline + speculative) menghasilkan JSONL valid (`docs/NOTES.md`); tinggal smoke run di Mac dengan `powermetrics`. |
| T08 | Validasi skema + perhitungan energi | B → A | T07 | IN PROGRESS | Unit test dan review silang lulus. Unit test lulus di CI; review silang diganti checklist D-007; tinggal cek `power_coverage` dan `J/token` dari smoke run Mac. |
| T09 | Jalankan Eksperimen A | A | T06–T08 | TODO | Record lengkap atau exception terdokumentasi. |
| T10 | Audit data Eksperimen A | B → A | T09 | TODO | Ringkasan valid/fail dan outlier dicatat. |
| T11 | Jalankan Eksperimen B | A | T06–T10 | TODO | Baseline dan enam variasi speculative tercatat. |
| T12 | Agregasi dan grafik | B → A | T09, T11 | IN PROGRESS | CSV summary dan dua grafik terbuat ulang dari source. `src/aggregate.py` dan `src/plot.py` sudah ada (dites dengan data sintetis); menunggu data T09/T11. |
| T13 | README/reproducibility audit | A | T12 | IN PROGRESS | Rekan dapat mengikuti instruksi smoke run dan angka konsisten. Clone baru `main` mengikuti README: test, dry-run, dan `scripts/run_mac.sh smoke` (disimulasikan di Linux) berjalan; tinggal angka asli dari Mac. |

## Urutan kritis

`T01 → T02/T04 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13`

`T03` dan `T05` dapat dikerjakan paralel sejak awal, tetapi keduanya perlu
selesai sebelum kontrak runner dan konfigurasi dibekukan.
