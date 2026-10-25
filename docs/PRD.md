# PRD — MLX Energy Benchmark

| Item | Nilai |
| --- | --- |
| Versi | 0.1 — draft untuk eksekusi |
| Pemilik | Tim benchmark (2 orang; sejak 2026-10-24 seluruhnya dikerjakan anggota A, D-007) |
| Target waktu | 5–9 Oktober 2026 — **sudah terlewati**; jadwal baru menunggu konfirmasi pengajar (D-005) |
| Platform | macOS pada Apple Silicon, MLX/Metal |
| Status | Implementasi selesai dan tervalidasi tanpa data daya; menunggu pengumpulan data di Mac (README, Urutan kerja di Mac) |

## 1. Ringkasan

Proyek ini menghasilkan benchmark lokal yang mengukur **throughput generasi**,
**memori puncak**, dan **energi per token keluaran** untuk beberapa ukuran dan
presisi model Qwen3 di MLX. Benchmark juga membandingkan decoding biasa dengan
speculative decoding menggunakan draft model. Seluruh hasil, prompt, konfigurasi,
skrip, grafik, dan batasan harus dapat ditinjau serta direproduksi dari Git.

Hasil baseline speculative decoding ini akan menjadi pembanding yang adil bagi
Project 3 ketika draft model biasa diganti dengan DFlash. Project ini sendiri
tidak mengimplementasikan atau mengevaluasi DFlash.

## 2. Latar belakang dan masalah

Pengujian satu kali dengan model default hanya menunjukkan bahwa MLX bisa
berjalan; ia tidak menjawab model mana yang lebih cepat atau lebih hemat energi.
Perbedaan ukuran model, bf16/8-bit/4-bit, dan penggunaan draft model dapat
mengubah biaya inferensi secara material. Tanpa prompt, warm-up, parameter
decoding, dan metode energi yang terkendali, perbandingan tersebut tidak valid.

Pengguna utama adalah dua anggota tim dan pengajar/reviewer yang perlu menilai
hasil eksperimen secara transparan. Jika benchmark tidak reproducible, angka
throughput dan energi tidak dapat dipercaya maupun dipakai untuk Project 3.

## 3. Tujuan dan ukuran keberhasilan

### Tujuan

1. Menghasilkan satu pipeline benchmark yang menjalankan semua konfigurasi
   memakai prompt dan parameter decoding yang sama.
2. Menghasilkan data mentah per-run dan tabel agregat untuk throughput,
   peak memory, serta `J/token`.
3. Mengukur sembilan konfigurasi ukuran × presisi yang layak pada mesin target.
4. Membandingkan baseline non-speculative dengan speculative decoding pada
   target Qwen3-4B dan draft Qwen3-0.6B-4bit untuk `k = 2, 4, 8`.
5. Mendokumentasikan implementasi MLX yang relevan agar cara kerja speculative
   decoding tidak hanya diasumsikan dari output CLI.

### Kriteria sukses

| Metrik | Ambang selesai |
| --- | --- |
| Reproducibility | Orang kedua dapat menjalankan satu smoke benchmark dari instruksi README tanpa mengubah kode. |
| Cakupan eksperimen A | Semua konfigurasi yang didukung sumber daya diuji; konfigurasi yang dilewati memiliki alasan tertulis. |
| Cakupan eksperimen B | Dua target precision × tiga nilai `k`, masing-masing dibandingkan dengan baseline tanpa draft. |
| Kualitas data | Setiap baris hasil memuat konfigurasi, prompt ID, nomor run, metrik, dan status; warm-up tidak tercampur dengan data analisis. |
| Deliverable | Dua grafik, tabel ringkasan, `NOTES.md`, dan README tersedia serta konsisten dengan data. |

### Metrik keberhasilan operasional

| Jenis | Metrik | Target | Cara ukur |
| --- | --- | --- | --- |
| Leading | Smoke run berhasil | 1/1 command smoke menghasilkan record valid | Validasi skema JSONL pada CI/lokal. |
| Leading | Kelengkapan matriks | 100% konfigurasi planned berstatus measured, skipped, atau failed dengan alasan | Audit `summary.csv` terhadap config. |
| Leading | Kelengkapan record | ≥ 95% record terencana valid; sisanya memiliki error eksplisit | Hitung status per konfigurasi/prompt/run. |
| Leading | Review silang | 100% perubahan kontrak data/energi direview anggota lain | Pull request atau catatan review. |
| Lagging | Reproducibility | Rekan menjalankan smoke benchmark tanpa perubahan kode | Checklist audit sebelum rilis. |
| Lagging | Kegunaan baseline | Hasil dapat dipakai sebagai baseline Project 3 tanpa perubahan workload/definisi metrik | Review lintas dokumen pada rilis. |

## 4. Ruang lingkup

### In scope (P0)

- Benchmark generasi batch size 1 melalui `mlx_lm.stream_generate`.
- Model Qwen3 ukuran 0.6B, 1.7B, dan 4B dalam bf16, 8-bit, dan 4-bit, sejauh
  model tersedia dan mesin memiliki RAM/disk yang cukup.
- Pengukuran daya chip memakai `powermetrics` untuk menghitung estimasi
  energi tambahan di atas idle.
- Satu warm-up per model/konfigurasi yang dikeluarkan dari hasil analisis.
- Tiga pengulangan per prompt dan konfigurasi setelah warm-up.
- Sekitar 10 prompt GSM8K yang sama, deterministik, dan diberi ID.
- Eksperimen standard speculative decoding dan pencatatan acceptance/draft
  fraction apabila API MLX menyediakannya.
- Grafik throughput dan `J/token`, tabel agregat, serta dokumentasi keterbatasan.

### Di luar scope versi ini

- Evaluasi akurasi lengkap atau benchmarking GSM8K end-to-end. Prompt GSM8K
  dipakai sebagai workload yang konsisten, bukan klaim kemampuan matematis.
- DFlash, pelatihan model, fine-tuning, atau perubahan backend MLX. Itu adalah
  kelanjutan Project 3.
- Batch size lebih dari 1, multi-user serving, atau benchmark lintas perangkat.
- Pengukuran daya komponen yang benar-benar terisolasi per model/proses;
  `powermetrics` tidak menyediakan isolasi tersebut.
- Dashboard web atau UI interaktif; Markdown, JSONL/CSV, dan gambar statis
  sudah cukup untuk deliverable.

## 5. Persona dan user stories

### Operator eksperimen

- Sebagai operator, saya ingin menjalankan satu konfigurasi dari command line
  agar dapat memperoleh hasil terstruktur tanpa menyalin angka manual.
- Sebagai operator, saya ingin benchmark menolak konfigurasi atau data yang
  tidak valid agar hasil tidak diam-diam rusak.
- Sebagai operator, saya ingin melanjutkan eksperimen yang terhenti tanpa
  menimpa hasil run sebelumnya.

### Analis/reviewer

- Sebagai analis, saya ingin mengetahui konfigurasi lengkap di setiap hasil
  agar perbedaan angka dapat ditelusuri.
- Sebagai reviewer, saya ingin melihat metode pengukuran dan keterbatasannya
  agar dapat menginterpretasikan grafik secara tepat.
- Sebagai anggota Project 3, saya ingin baseline speculative decoding standar
  dengan prompt dan mesin yang sama agar DFlash dapat dibandingkan secara adil.

## 6. Persyaratan fungsional

### P0 — wajib sebelum dianggap selesai

| ID | Kebutuhan | Kriteria penerimaan |
| --- | --- | --- |
| FR-01 | CLI benchmark menerima model target, path prompt, jumlah output token, jumlah run, dan lokasi output. | `--help` menjelaskan semua argumen; satu perintah menghasilkan baris data JSONL. |
| FR-02 | Skrip selalu memakai model eksplisit, tidak mengandalkan model default. | ID model tercatat pada setiap hasil dan README. |
| FR-03 | Skrip menjalankan warm-up dan tidak memasukkannya ke statistik. | Baris warm-up tidak berstatus `measured`; data agregat hanya membaca `measured`. |
| FR-04 | Semua konfigurasi memakai set prompt dan decoding yang tetap. | Prompt memiliki ID stabil; seed/temperature/max token dicatat pada hasil. |
| FR-05 | Skrip mencatat throughput generasi, jumlah token, peak memory, waktu mulai/selesai, serta konfigurasi. | Setiap baris JSON memenuhi skema yang terdokumentasi. |
| FR-06 | Skrip mencatat baseline idle, daya rata-rata selama run, dan estimasi `joules_per_token`. | Bila sampel daya tidak ada, run diberi status gagal/tidak lengkap dan tidak dipakai grafik. |
| FR-07 | Skrip mendukung target saja dan target + draft model dengan nilai `k`. | Hasil speculative memuat draft model, `k`, dan draft fraction bila didukung versi API. |
| FR-08 | Agregator/plot menghasilkan tabel ringkasan dan dua grafik wajib. | Grafik dapat diregenerasi dari data committed dan command README. |
| FR-09 | `NOTES.md` menjawab empat pertanyaan reverse engineering atas versi `generate.py` yang dipakai. | Catatan menyebut path/commit atau versi sumber serta tidak sekadar menyalin kode. |

### P1 — dikerjakan jika waktu memungkinkan

| ID | Kebutuhan | Kriteria penerimaan |
| --- | --- | --- |
| FR-10 | Urutan konfigurasi dan prompt dapat diacak dengan seed tercatat. | Seed dan urutan aktual dicatat; opsi default didokumentasikan. |
| FR-11 | Skrip resume menghindari duplikasi `(experiment_id, config_id, prompt_id, run)`. | Menjalankan ulang tidak menambah baris identik tanpa flag eksplisit. |
| FR-12 | Validasi skema serta unit test perhitungan energi tersedia. | Test dapat dijalankan lokal dan lulus. |
| FR-13 | Metadata kondisi run (versi macOS, MLX, RAM, waktu) direkam otomatis. | Metadata tersedia dalam manifest, bukan hanya narasi README. |

### P2 — pertimbangan masa depan

- Tambahkan evaluasi kualitas jawaban/GSM8K untuk membandingkan efisiensi dan
  kualitas secara bersamaan.
- Tambahkan DFlash sebagai draft backend Project 3 melalui antarmuka konfigurasi
  yang sama.
- Bandingkan beberapa perangkat Apple Silicon dengan manifest mesin per host.

## 7. Desain eksperimen

### Variabel terkendali

- Perangkat: satu mesin Apple Silicon, mode daya/kondisi sistem dicatat.
- Backend: MLX dengan Python 3.12; `mlx 0.32.3` dan `mlx-lm 0.32.1` di-pin di
  `requirements.txt` (D-008, menggantikan build dev `0.32.1.dev6`).
- Workload: sekitar 10 prompt GSM8K dari `prompts/gsm8k_10.jsonl`.
- Generation: non-thinking untuk Qwen3 (`enable_thinking=False` pada chat
  template, tercatat di setiap record), temperature 0, max output tokens 256
  kecuali dicatat berbeda.
- Batch size: 1.
- Repetisi: tiga run terukur per prompt; warm-up dibuang.

### Eksperimen A — ukuran × presisi

Konfigurasi target: 0.6B, 1.7B, dan 4B × bf16, 8-bit, 4-bit (9 konfigurasi).
Jika Qwen3-4B bf16 tidak dapat dimuat karena batas RAM, dokumentasikan sebagai
`skipped_resource_limit`, sertakan alasan dan bukti singkat; jangan mengganti
diam-diam dengan model lain.

### Eksperimen B — speculative decoding standar

Target: Qwen3-4B bf16 dan 4-bit. Draft: Qwen3-0.6B-4bit. Nilai `k`: 2, 4, 8.
Setiap target precision harus memiliki baseline tanpa draft pada workload yang
sama. Konfigurasi valid hanya bila versi MLX yang dipasang mendukung argumen
draft; nama field dan argument diverifikasi sebelum pengumpulan data.

Jika Qwen3-4B bf16 berstatus `skipped_resource_limit` pada Eksperimen A, target
bf16 pada Eksperimen B diganti Qwen3-4B 8-bit dengan experiment ID tersendiri
dan dicatat di `docs/DECISIONS.md` (D-004). Target 4-bit tidak berubah.

Dengan temperature 0, speculative decoding seharusnya menghasilkan teks yang
sama dengan baseline target tanpa draft. Setiap run menyimpan `output_sha256`;
hash yang berbeda dari baseline untuk prompt yang sama wajib diselidiki
sebelum data dipakai.

### Metode energi

`powermetrics` membaca daya gabungan CPU + GPU + ANE dalam mW, dengan interval
sampling **100 ms** (D-002). Run model kecil dapat selesai dalam 1–2 detik,
sehingga interval 500 ms hanya memberi 2–4 sampel per run.

- **Jendela run (`duration_s`)**: waktu dinding dari pemanggilan
  `stream_generate` sampai token terakhir, **termasuk prefill** (D-003).
  Tokenisasi/chat template dan pemuatan model di luar jendela.
- **Daya rata-rata run**: setiap sampel diletakkan pada sumbu waktu dan
  dibobot dengan lamanya tumpang-tindih dengan jendela run, bukan sekadar
  rata-rata sampel yang tiba selama run.
- **Cakupan**: porsi jendela run yang tertutup sampel (`power_coverage`).
  Run dengan cakupan < 0,9 berstatus `incomplete` dan tidak masuk grafik.
- **Idle**: diukur 20 detik di awal blok, lalu diukur ulang 10 detik setiap
  10 run terukur untuk menangkap drift thermal. Setiap record menyimpan nilai
  idle yang dipakai.

```text
energi tambahan (J) = max(daya_rata-rata_run - daya_idle, 0) × durasi_run
J/token = energi tambahan / jumlah_token_keluaran
```

Nilai negatif setelah pengurangan idle menjadi 0 sesuai definisi ini, dan
ditandai `energy_clipped: true`. Jumlah run yang terpotong wajib dilaporkan per
konfigurasi karena pemotongan membuat rata-rata bias ke atas.

## 8. Skema data minimum

Satu baris `data/raw/results.jsonl` mewakili satu run (terukur, warm-up,
gagal, tidak lengkap, atau dilewati). Definisi tipe dan aturan validasi ada di
`src/schemas.py`; jalankan `python -m src.schemas FILE.jsonl` untuk memeriksa
file. Warm-up memakai `run: -1`. Field:

```json
{
  "schema_version": 1,
  "experiment_id": "A-size-precision",
  "config_id": "qwen3-0.6b-4bit",
  "model": "mlx-community/Qwen3-0.6B-4bit",
  "draft_model": null,
  "num_draft_tokens": null,
  "prompt_id": "gsm8k-001",
  "run": 0,
  "status": "measured",
  "temperature": 0.0,
  "seed": 0,
  "max_tokens": 256,
  "enable_thinking": false,
  "generation_tokens": 0,
  "generation_tps": 0.0,
  "prompt_tokens": 0,
  "prompt_tps": 0.0,
  "peak_memory_gb": 0.0,
  "idle_watts": 0.0,
  "avg_watts": 0.0,
  "duration_s": 0.0,
  "joules_per_token": 0.0,
  "energy_clipped": false,
  "power_interval_ms": 100,
  "power_samples": 0,
  "power_coverage": 0.0,
  "draft_fraction": null,
  "output_sha256": "<sha256 teks keluaran>",
  "started_at": "2026-10-05T00:00:00+07:00",
  "finished_at": "2026-10-05T00:00:02+07:00",
  "error": null
}
```

Raw data berskala besar dan log dapat diabaikan Git; hasil final yang menjadi
dasar grafik harus dipublikasikan sebagai `data/processed/summary.csv` dan
`data/processed/results_final.jsonl`.

## 9. Kebutuhan nonfungsional dan batasan

- **Reproducible:** command yang sama pada kondisi mesin setara menghasilkan
  artefak dengan struktur dan skema yang sama; angka performa dapat bervariasi.
- **Traceable:** model ID, versi paket, konfigurasi, prompt ID, dan waktu run
  harus dapat dicocokkan kembali.
- **Aman:** token Hugging Face tidak boleh masuk Git, output, atau screenshot.
- **Portabel secara terbatas:** kode ditulis Python, tetapi power measurement
  secara eksplisit bergantung pada macOS `powermetrics` dan Apple Silicon.
- **Resource-aware:** cek disk dan RAM sebelum mengunduh/menjalankan semua
  model; estimasi awal keseluruhan unduhan sekitar puluhan GB.

Keterbatasan yang wajib muncul pada README dan laporan:

1. `powermetrics` mengukur seluruh chip, bukan energi proses/model saja.
2. Energi prefill/prompt ikut dihitung, sedangkan metrik utama dibagi token
   keluaran.
3. Semua angka dibuat pada batch size 1.
4. Urutan run, suhu/thermal throttling, aktivitas latar belakang, dan interval
   sampling dapat memengaruhi hasil.

## 10. Deliverable dan definisi selesai

Project 4 selesai bila Git berisi:

- implementasi benchmark dan plot yang dapat dijalankan;
- prompt dataset yang tetap dan berlisensi/beratribusi dengan benar;
- data final dan tabel ringkasan;
- dua grafik wajib;
- `docs/NOTES.md` hasil reverse engineering;
- README dengan spesifikasi mesin, instalasi, command reproduksi, hasil, dan
  keterbatasan;
- bukti test/smoke run dan review rekan.

Tidak ada deliverable yang dianggap selesai hanya karena command berhasil sekali.

## 11. Jadwal dan dependensi

| Fase | Hasil | Penanggung jawab utama | Target |
| --- | --- | --- | --- |
| 0. Setup dan validasi | environment, model ID, test `powermetrics` | A | Hari 1 |
| 1. Pemahaman API | `docs/NOTES.md`, keputusan API draft | B | Hari 1 |
| 2. Implementasi | `bench.py`, parser daya, skema hasil | A dengan review B | Hari 2 |
| 3. Validasi | smoke test, unit test, dry run | B dengan perbaikan A | Hari 2 |
| 4. Pengumpulan | eksperimen A dan B, manifest run | A menjalankan; B memantau data | Hari 3 |
| 5. Analisis | agregasi, grafik, interpretasi | B dengan review A | Hari 4 |
| 6. Rilis | README final, audit reproduksibilitas | bersama | Hari 5 |

Ketergantungan utama: akses model Hugging Face, disk/RAM memadai, hak `sudo`
untuk `powermetrics`, dan kompatibilitas API speculative decoding pada versi MLX.
Jika salah satu gagal, tim harus mencatat dampak dan melakukan scope adjustment
tertulis di `docs/DECISIONS.md`.

## 12. Pertanyaan terbuka

| Pertanyaan | Pemilik | Dampak | Status |
| --- | --- | --- | --- |
| ID repository MLX Community mana yang persis dipakai untuk tiap varian Qwen3? | A | Memblokir pengumpulan data | Terjawab: 9 repo `mlx-community/Qwen3-{0.6B,1.7B,4B}-{bf16,8bit,4bit}`, di-pin per commit di `config/defaults.yaml` |
| Apakah `GenerationResponse` versi terpasang menyediakan `from_draft` dan `peak_memory` dengan nama tersebut? | B → A | Memblokir metrik draft fraction | Terjawab: ya pada `mlx-lm` 0.32.1 yang di-pin (D-008; `peak_memory` dalam GB), diverifikasi dengan smoke run; lihat `docs/NOTES.md` |
| Regex `powermetrics` apa yang cocok dengan versi macOS mesin target? | A | Memblokir pengukuran energi | Terbuka |
| Berapa RAM, ruang disk, dan versi macOS mesin target? | A | Menentukan konfigurasi yang feasible | Terbuka |
| Tenggat 9 Oktober 2026 sudah lewat; kapan tenggat barunya? | Tim/pengajar | Menentukan scope P1 | Terbuka (D-005) |

## 13. Struktur repositori yang disetujui

```text
.
├── README.md
├── .gitignore
├── requirements.txt                 # pin dependency proyek setelah tervalidasi
├── requirements-dev.txt             # dependensi test (tanpa MLX), dipakai CI
├── .github/workflows/tests.yml      # pytest di setiap PR dan push ke main
├── src/
│   ├── bench.py                     # CLI pengumpul metrik per run
│   ├── experiments.py               # jalankan matriks dari config/*.yaml
│   ├── power.py                     # pembaca/parsing powermetrics
│   ├── schemas.py                   # model/skema record hasil
│   ├── aggregate.py                 # membuat tabel agregat
│   └── plot.py                      # membuat grafik final
├── config/
│   ├── experiment_a.yaml            # ukuran × presisi
│   ├── experiment_b.yaml            # speculative decoding
│   └── defaults.yaml                # decoding, path default, registry model
├── prompts/
│   ├── gsm8k_10.jsonl               # workload canonical, tracked
│   └── README.md                    # asal, lisensi, dan format prompt
├── data/
│   ├── raw/                         # JSONL/log mentah, umumnya tidak tracked
│   ├── processed/
│   │   ├── results_final.jsonl       # subset final yang mendasari laporan
│   │   └── summary.csv               # agregat yang tracked
│   └── manifests/                    # metadata environment dan command run
├── plots/
│   ├── throughput_by_model_size.png
│   ├── energy_per_token.png
│   └── speculative_by_k.png         # Eksperimen B (tambahan)
├── tests/
│   ├── test_power_parser.py
│   ├── test_energy.py
│   ├── test_power_monitor.py
│   ├── test_bench_helpers.py
│   ├── test_experiments.py
│   ├── test_aggregate.py
│   ├── test_plot.py
│   ├── test_prompts.py
│   ├── test_result_schema.py
│   └── fixtures/                    # contoh output powermetrics
└── docs/
    ├── PRD.md
    ├── EXPERIMENT_PLAN.md
    ├── TEAM_WORKFLOW.md
    ├── TASK_BOARD.md
    ├── NOTES.md
    └── DECISIONS.md
```

Folder `data/raw/` dan `plots/` memiliki `.gitkeep` agar strukturnya terlihat
sebelum artefak final dibuat. Hanya artefak final yang direview dan diperlukan
untuk reproduksi yang dipush; data mentah dapat diarsipkan terpisah bila besar.
