# Cara Kerja Tim Dua Orang

Tujuan dokumen ini adalah mencegah eksperimen berjalan di dua arah yang berbeda
atau data sulit digabungkan.

## Peran utama

| Area | Anggota A — Infrastruktur & eksekusi | Anggota B — Validasi & analisis |
| --- | --- | --- |
| Environment, model, dan `powermetrics` | Memimpin | Review |
| Reverse engineering MLX / `NOTES.md` | Review | Memimpin |
| `src/bench.py`, `src/power.py` | Memimpin | Review/test |
| Skema hasil dan validasi | Implementasi bersama | Memimpin review |
| Menjalankan matriks eksperimen | Memimpin | Audit data dan log |
| Agregasi, grafik, interpretasi | Review | Memimpin |
| README dan final check | Bersama | Bersama |

Kepemilikan bukan pembatas: setiap perubahan yang menyentuh kontrak data,
parameter eksperimen, atau perhitungan energi harus direview anggota lain.

## Aturan Git

1. `main` hanya menerima perubahan yang dapat dijalankan atau dokumentasi yang
   konsisten. Hindari commit setengah jadi yang merusak flow utama.
2. Gunakan branch pendek: `codex/setup`, `codex/bench`, `codex/power-parser`,
   `codex/analysis`, dan sejenisnya.
3. Satu branch sebaiknya berfokus pada satu area. Jangan sekaligus mengubah
   parser daya, model matrix, dan grafik tanpa alasan.
4. Commit message menjelaskan dampak, misalnya `feat: record per-run power
   metrics` atau `docs: define speculative benchmark matrix`.
5. Sebelum merge, author menjalankan test relevan; reviewer memeriksa skema,
   reproduksibilitas, dan apakah perubahan memengaruhi data sebelumnya.
6. Tidak ada token Hugging Face, password `sudo`, path pribadi, model cache,
   atau data mentah besar dalam Git.

## Kontrak handoff

Sebelum menyerahkan pekerjaan ke rekan, sertakan:

- branch/commit yang menjadi dasar;
- command yang sudah dijalankan;
- hasil yang diharapkan dan hasil aktual;
- perubahan skema atau asumsi baru;
- blocker atau keputusan yang masih terbuka.

Contoh handoff ringkas:

```text
Branch: codex/power-parser
Validated: pytest tests/test_power_parser.py
Output: parser mengubah "Combined Power ... 1234 mW" menjadi 1.234 W
Open: format output powermetrics pada macOS target belum dipastikan
```

## Ritme kerja harian

- Awal hari: pilih satu tugas prioritas per orang dari `TASK_BOARD.md` dan
  tandai pemilik/status.
- Setelah perubahan kontrak: sync 10 menit untuk menyepakati skema/parameter.
- Sebelum eksperimen panjang: lakukan smoke test yang direview rekan.
- Akhir hari: commit pekerjaan, update board, dan tulis keputusan penting pada
  `DECISIONS.md`.

## Aturan keputusan eksperimen

1. Prompt, model ID, max tokens, sampling, dan jumlah run tidak boleh berubah
   di tengah satu experiment ID.
2. Perubahan perlu membuat experiment ID baru atau membatalkan hasil blok lama
   secara eksplisit—bukan mencampur data.
3. Jika sumber daya tidak cukup untuk konfigurasi wajib, catat konfigurasi
   sebagai skipped dengan alasan, bukti, dan dampak pada kesimpulan.
4. Outlier tidak boleh dihapus hanya karena tidak sesuai harapan. Tandai,
   selidiki, lalu putuskan dengan catatan.
