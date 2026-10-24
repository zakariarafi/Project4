# Rencana Eksperimen

Dokumen ini menerjemahkan PRD menjadi prosedur eksekusi. Detail kebutuhan dan
ruang lingkup ada di [PRD.md](PRD.md).

## Urutan sebelum mengumpulkan data

1. Buat virtual environment proyek dengan Python 3.12. Jangan mengubah Python
   sistem dan jangan menaruh implementasi proyek di clone `mlx-lm`.
2. Catat `python --version`, `pip show mlx mlx-lm`, chip, RAM, versi macOS,
   sisa disk, dan git revision/versi source `mlx-lm` pada manifest lingkungan.
3. Model ID MLX Community dan commit-nya sudah di-pin di
   `config/defaults.yaml`. Semua command benchmark memakai identifier model
   eksplisit; jalankan matriks lewat `python -m src.experiments`.
4. Jalankan `mlx_lm.generate --help` dan periksa flag draft. Baca source
   `mlx_lm/generate.py`; tulis temuannya di `docs/NOTES.md`.
5. Jalankan `sudo powermetrics --samplers cpu_power,gpu_power -i 100 -n 5`.
   Simpan output non-rahasia di `tests/fixtures/powermetrics_<macos>.txt`,
   tambahkan test parser untuk file itu, dan pastikan `pytest` lulus.
   Fixture saat ini masih sintetis.
6. Buat/validasi sepuluh prompt canonical dengan ID tetap. Jangan mengedit
   prompt setelah data pertama terkumpul tanpa mengganti versi experiment ID.
7. Jalankan smoke test satu model, satu prompt, satu run (perintah ada di
   README). Periksa JSONL dengan `python -m src.schemas`, perhitungan energi,
   dan `power_coverage`. Cakupan yang rendah padahal `powermetrics` berjalan
   menandakan output tertahan buffer pipe; catat di `docs/DECISIONS.md`.

## Protokol run

Untuk setiap konfigurasi:

1. Tutup aplikasi yang tidak perlu dan catat kondisi yang relevan.
2. Jalankan `sudo -v` di awal sesi agar `powermetrics` tidak berhenti meminta
   password di tengah benchmark.
3. Mulai pencatatan daya dan ukur idle selama minimal 20 detik. Runner
   mengukur ulang idle 10 detik setiap 10 run terukur.
4. Muat model dan jalankan satu warm-up pendek. Jangan simpan sebagai hasil
   terukur.
5. Jalankan 3 pengulangan untuk setiap prompt. Urutannya pengulangan di luar
   dan prompt di dalam, agar drift waktu tersebar ke semua prompt. Simpan
   record atomik per run.
6. Jika satu run gagal, tulis record `status: failed` beserta error ringkas;
   jangan menghapus jejak kegagalan atau menggantinya diam-diam.
7. Setelah satu blok selesai, periksa jumlah record yang diharapkan, data null,
   dan outlier yang jelas. Catat restart/thermal issue dalam manifest.

## Matriks

### A — ukuran dan presisi

| Model | bf16 | 8-bit | 4-bit |
| --- | :---: | :---: | :---: |
| Qwen3-0.6B | wajib | wajib | wajib |
| Qwen3-1.7B | wajib | wajib | wajib |
| Qwen3-4B | wajib jika feasible | wajib | wajib |

Target nominal: `9 konfigurasi × 10 prompt × 3 run = 270` record terukur.
Setiap konfigurasi juga memiliki satu warm-up yang tidak masuk target tersebut.

### B — standard speculative decoding

| Target | Draft | k | Baseline |
| --- | --- | --- | --- |
| Qwen3-4B bf16 | Qwen3-0.6B 4-bit | 2, 4, 8 | target tanpa draft |
| Qwen3-4B 4-bit | Qwen3-0.6B 4-bit | 2, 4, 8 | target tanpa draft |

Cadangan: jika Qwen3-4B bf16 tidak dapat dimuat, baris pertama diganti
Qwen3-4B 8-bit dengan experiment ID baru (D-004).

Target nominal speculative: `6 konfigurasi × 10 prompt × 3 run = 180` record
terukur, ditambah dua baseline (60 record). Baseline dijalankan ulang di
experiment ID B agar kondisi sesinya sama dengan run speculative (D-006);
angka baseline dari Eksperimen A tidak dipakai sebagai pembanding B.

## Kriteria kualitas sebelum agregasi

- Tidak ada record `measured` yang kehilangan model, prompt ID, run, atau token
  keluaran.
- `generation_tokens > 0`, durasi positif, dan `generation_tps` masuk akal.
- `joules_per_token` hanya dihitung jika `power_coverage ≥ 0,9`.
- Jumlah run `energy_clipped: true` dilaporkan per konfigurasi.
- `output_sha256` run speculative sama dengan baseline target untuk prompt
  yang sama (temperature 0); perbedaan diselidiki sebelum agregasi.
- Konfigurasi speculative menyimpan draft model dan `k`; draft fraction `null`
  hanya diperbolehkan bila API yang terverifikasi memang tidak mengeksposnya.
- Nilai ekstrem tidak dihapus tanpa alasan tertulis di `docs/DECISIONS.md`.

## Agregasi dan pelaporan

Agregator menghitung paling sedikit rata-rata, median, standar deviasi, jumlah
run valid, dan jumlah gagal per konfigurasi. Tabel final harus membedakan
baseline dan speculative decoding. Grafik menggunakan nilai agregat, bukan satu
run terbaik.

Sebelum commit final, verifikasi bahwa angka pada README sama dengan
`data/processed/summary.csv` dan grafik dapat dibuat ulang dari command yang
didokumentasikan.
