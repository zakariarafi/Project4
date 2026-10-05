# MLX Energy Benchmark

Benchmark yang dapat direproduksi untuk mengevaluasi dampak ukuran model,
presisi/kuantisasi, dan speculative decoding terhadap throughput, memori, dan
energi inferensi LLM lokal melalui MLX pada perangkat Apple Silicon.

Dokumen utama proyek ada di [docs/PRD.md](docs/PRD.md). Rencana kerja dua
orang, definisi eksperimen, dan aturan kolaborasi diringkas di:

- [docs/EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md)
- [docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md)
- [docs/TASK_BOARD.md](docs/TASK_BOARD.md)

> Status: perencanaan. `mlx-lm` telah tervalidasi berjalan pada Python 3.12,
> tetapi benchmark belum dimulai.

## Struktur singkat

```text
src/       implementasi benchmark dan visualisasi
config/    konfigurasi eksperimen yang dapat ditinjau
prompts/   set prompt tetap untuk semua konfigurasi
data/      hasil eksperimen terstruktur
tests/     pemeriksaan parser, skema, dan perhitungan
docs/      PRD, prosedur, dan catatan keputusan
```

Lihat [docs/PRD.md#struktur-repositori-yang-disetujui](docs/PRD.md#struktur-repositori-yang-disetujui)
untuk struktur lengkap dan kebijakan berkas yang boleh masuk Git.
