# MLX Energy Benchmark

Benchmark yang dapat direproduksi untuk mengevaluasi dampak ukuran model,
presisi/kuantisasi, dan speculative decoding terhadap throughput, memori, dan
energi inferensi LLM lokal melalui MLX pada perangkat Apple Silicon.

Dokumen utama proyek ada di [docs/PRD.md](docs/PRD.md). Rencana kerja dua
orang, definisi eksperimen, dan aturan kolaborasi diringkas di:

- [docs/EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md)
- [docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md)
- [docs/TASK_BOARD.md](docs/TASK_BOARD.md)

> Status: implementasi awal. Runner, parser `powermetrics`, dan validator skema
> sudah tersedia dan dites di luar Mac; smoke run di Mac target belum dilakukan.

## Menjalankan

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# test (tidak butuh Mac/MLX)
python -m pytest

# smoke run: satu model, satu prompt, satu run
sudo -v   # powermetrics dijalankan dengan `sudo -n`
python -m src.bench \
    --experiment-id smoke --config-id qwen3-0.6b-4bit \
    --model mlx-community/Qwen3-0.6B-4bit \
    --limit-prompts 1 --runs 1 --output data/raw/smoke.jsonl
python -m src.schemas data/raw/smoke.jsonl

# speculative decoding (Eksperimen B)
python -m src.bench \
    --experiment-id B-speculative --config-id qwen3-4b-4bit-k4 \
    --model mlx-community/Qwen3-4B-4bit \
    --draft-model mlx-community/Qwen3-0.6B-4bit --num-draft-tokens 4

# konfigurasi yang tidak muat di RAM: catat alasannya, jangan diganti diam-diam
python -m src.bench --experiment-id A-size-precision --config-id qwen3-4b-bf16 \
    --model mlx-community/Qwen3-4B-bf16 --skip-reason "RAM 16 GB tidak cukup"
```

ID model di atas masih contoh dan perlu divalidasi (T02). `--no-power` bisa
dipakai untuk menguji pipeline tanpa `sudo`, tetapi run-nya berstatus
`incomplete` dan tidak masuk analisis. Lihat `python -m src.bench --help`.

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
