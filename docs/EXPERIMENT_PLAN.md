# Rencana Eksperimen

Dokumen ini menerjemahkan PRD menjadi prosedur eksekusi. Detail kebutuhan dan
ruang lingkup ada di [PRD.md](PRD.md).

## Urutan sebelum mengumpulkan data

1. Buat virtual environment proyek dengan Python 3.12. Jangan mengubah Python
   sistem dan jangan menaruh implementasi proyek di clone `mlx-lm`.
2. Catat `python --version`, `pip show mlx mlx-lm`, chip, RAM, versi macOS,
   sisa disk, dan git revision/versi source `mlx-lm` pada manifest lingkungan.
3. Tentukan model ID MLX Community yang benar. Semua command benchmark wajib
   memakai identifier model eksplisit.
4. Jalankan `mlx_lm.generate --help` dan periksa flag draft. Baca source
   `mlx_lm/generate.py`; tulis temuannya di `docs/NOTES.md`.
5. Jalankan `sudo powermetrics --samplers cpu_power,gpu_power -i 500 -n 3`.
   Simpan satu contoh output non-rahasia dan pastikan regex parser bekerja.
6. Buat/validasi sepuluh prompt canonical dengan ID tetap. Jangan mengedit
   prompt setelah data pertama terkumpul tanpa mengganti versi experiment ID.
7. Jalankan smoke test satu model, satu prompt, satu run. Periksa JSONL,
   perhitungan energi, dan status power samples.

## Protokol run

Untuk setiap konfigurasi:

1. Tutup aplikasi yang tidak perlu dan catat kondisi yang relevan.
2. Jalankan `sudo -v` di awal sesi agar `powermetrics` tidak berhenti meminta
   password di tengah benchmark.
3. Mulai pencatatan daya dan ukur idle selama minimal 20 detik.
4. Muat model dan jalankan satu warm-up pendek. Jangan simpan sebagai hasil
   terukur.
5. Jalankan 3 pengulangan untuk setiap prompt. Simpan record atomik per run.
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

Target nominal speculative: `6 konfigurasi × 10 prompt × 3 run = 180` record
terukur, ditambah dua baseline (60 record) bila belum tersedia dari Eksperimen A.

## Kriteria kualitas sebelum agregasi

- Tidak ada record `measured` yang kehilangan model, prompt ID, run, atau token
  keluaran.
- `generation_tokens > 0`, durasi positif, dan `generation_tps` masuk akal.
- `joules_per_token` hanya dihitung jika sampel daya tersedia.
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
