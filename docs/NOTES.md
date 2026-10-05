# Catatan Reverse Engineering MLX

> Isi dokumen ini setelah memeriksa source `mlx_lm/generate.py` dari versi yang
> benar-benar dipakai benchmark. Jangan menyalin contoh dari instruksi tanpa
> verifikasi.

## Metadata source

- Path source:
- Git commit/tag atau versi `mlx-lm`:
- Tanggal pemeriksaan:
- Pemeriksa:

## 1. `GenerationResponse`

Tuliskan field yang relevan: `prompt_tps`, `generation_tps`, `peak_memory`,
jumlah token, dan apakah tersedia penanda `from_draft`.

## 2. Penerimaan/penolakan token draft

Jelaskan alur pada `speculative_generate_step` dengan bahasa sendiri.

## 3. Propagasi argument draft

Jelaskan bagaimana `stream_generate` meneruskan `draft_model` dan
`num_draft_tokens`.

## 4. Antarmuka CLI

Tuliskan nama flag yang dilaporkan `mlx_lm.generate --help` dan contoh command
yang tervalidasi.

## Dampak pada benchmark

Dokumentasikan penyesuaian yang harus dibuat pada `src/bench.py`, termasuk
field yang tidak tersedia atau berbeda nama pada versi ini.
