# MLX Energy Benchmark

Benchmark yang dapat direproduksi untuk mengevaluasi dampak ukuran model,
presisi/kuantisasi, dan speculative decoding terhadap throughput, memori, dan
energi inferensi LLM lokal melalui MLX pada perangkat Apple Silicon.

Dokumen utama proyek ada di [docs/PRD.md](docs/PRD.md). Rencana kerja dua
orang, definisi eksperimen, dan aturan kolaborasi diringkas di:

- [docs/EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md)
- [docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md)
- [docs/TASK_BOARD.md](docs/TASK_BOARD.md)

> Status: kode, config, prompt, dan dokumentasi siap. Pipeline sudah dijalankan
> dengan MLX sungguhan di CPU Linux (tanpa pengukuran daya, lihat
> [docs/NOTES.md](docs/NOTES.md)); pengumpulan data di Mac Apple Silicon belum
> dilakukan.

## Menjalankan

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# test (tidak butuh Mac/MLX; juga dijalankan GitHub Actions di setiap PR)
pip install -r requirements-dev.txt   # cukup ini bila hanya menjalankan test
python -m pytest

# smoke run: satu model, satu prompt, satu run
sudo -v   # powermetrics dijalankan dengan `sudo -n`
python -m src.bench \
    --experiment-id smoke --config-id qwen3-0.6b-4bit \
    --model mlx-community/Qwen3-0.6B-4bit \
    --limit-prompts 1 --runs 1 --output data/raw/smoke.jsonl
python -m src.schemas data/raw/smoke.jsonl

# matriks eksperimen dari config/ (lihat dulu perintahnya dengan --dry-run)
python -m src.experiments config/experiment_a.yaml --dry-run
python -m src.experiments config/experiment_a.yaml
python -m src.experiments config/experiment_b.yaml --only qwen3-4b-4bit-k4
```

Setelah data terkumpul, buat tabel ringkasan dan grafik final:

```bash
python -m src.aggregate data/raw/results.jsonl \
    --expect config/experiment_a.yaml config/experiment_b.yaml
python -m src.plot
```

`src.aggregate` menolak input yang melanggar skema, berisi run duplikat, atau
mencampur parameter decoding dalam satu experiment ID. Hasilnya
`data/processed/summary.csv` (rata-rata, median, simpangan baku, jumlah run per
status, kelengkapan terhadap config, speedup dan rasio energi terhadap
baseline, serta jumlah output speculative yang berbeda dari baseline) dan
`data/processed/results_final.jsonl`. `src.plot` menulis
`plots/throughput_by_model_size.png`, `plots/energy_per_token.png`, dan
`plots/speculative_by_k.png` dari `summary.csv`.

## Urutan kerja di Mac

Semua langkah di bawah memerlukan Mac Apple Silicon yang tersambung ke
charger. Satu perintah menjalankan semuanya, dari Terminal di root repo:

```bash
bash scripts/run_mac.sh smoke   # langkah 1-4, berhenti setelah smoke run
bash scripts/run_mac.sh         # langkah 1-7; aman dijalankan ulang
```

Script meminta password `sudo` sekali, menyegarkan izin `sudo` tiap menit
(satu konfigurasi bisa lebih lama dari timeout `sudo` 5 menit), mencegah Mac
tidur dengan `caffeinate`, dan berhenti bila smoke run tidak menghasilkan run
`measured`.

### Menjalankan dari sesi Claude Code di Mac

Sesi Claude Code (atau `nohup`) tidak punya terminal untuk mengetik password,
jadi pasang dulu aturan `sudoers` yang mengizinkan **hanya**
`/usr/bin/powermetrics` tanpa password. Jalankan sekali di Terminal; file
divalidasi dengan `visudo` sebelum dipasang karena `sudoers` yang rusak bisa
mengunci `sudo`:

```bash
printf '%s ALL=(root) NOPASSWD: /usr/bin/powermetrics\n' "$(whoami)" > /tmp/powermetrics-benchmark
sudo visudo -cf /tmp/powermetrics-benchmark && \
  sudo install -m 440 -o root -g wheel /tmp/powermetrics-benchmark /etc/sudoers.d/powermetrics-benchmark
sudo -k; sudo -n powermetrics --samplers cpu_power -i 100 -n 1 >/dev/null && echo OK
```

Aturan ini memberi akses root ke `powermetrics` tanpa password, termasuk opsi
`-o` yang menulis file sebagai root. Hapus setelah eksperimen selesai:
`sudo rm /etc/sudoers.d/powermetrics-benchmark`. `scripts/run_mac.sh`
mendeteksi aturan ini dan melewati `sudo -v`.

Lalu buka Claude Code di folder repo (aplikasi Claude Desktop, atau
`claude remote-control` di Terminal) dan minta ia menjalankan
`bash scripts/run_mac.sh smoke`, lalu `bash scripts/run_mac.sh` di latar
belakang dengan log ke `data/raw/` dan memantaunya sampai selesai.

### Rincian langkah

Untuk dijalankan manual bila perlu (ID di kurung merujuk ke
[docs/TASK_BOARD.md](docs/TASK_BOARD.md)):

1. **Lingkungan (T01).** Buat venv dan `pip install -r requirements.txt`, lalu
   catat mesin:

   ````bash
   { echo '# Environment'; echo '```'; sw_vers; sysctl -n machdep.cpu.brand_string
     echo "RAM bytes: $(sysctl -n hw.memsize)"; df -h .; python --version
     pip show mlx mlx-lm | grep -E '^(Name|Version)'; echo '```'; } \
     > data/manifests/environment.md
   ````

2. **Kapasitas (T02).** Pastikan disk kosong > 30 GB (unduhan ±23 GB). Jika
   RAM tidak cukup untuk Qwen3-4B bf16 (±8 GB bobot), isi `skip_reason` pada
   entrinya di `config/experiment_a.yaml` dan terapkan D-004.
3. **`powermetrics` (T04).** Simpan output asli lalu jalankan test; file
   `powermetrics_macos*.txt` di `tests/fixtures/` otomatis ikut dites:

   ```bash
   sudo powermetrics --samplers cpu_power,gpu_power -i 100 -n 5 \
     > tests/fixtures/powermetrics_macos$(sw_vers -productVersion).txt
   python -m pytest tests/test_power_parser.py
   ```

4. **Smoke run (T07/T08).** Jalankan perintah smoke di atas tanpa `--no-power`,
   lalu `python -m src.smoke_check data/raw/smoke.jsonl`: harus ada run
   `measured` dengan `power_coverage` ≥ 0,9. Jika `incomplete` karena cakupan
   rendah, catat di `docs/DECISIONS.md` sebelum lanjut. Jalankan
   `while true; do sudo -n true; sleep 60; done &` agar izin `sudo` tidak
   habis di tengah eksperimen.
5. **Eksperimen A (T09) lalu audit (T10).** `python -m src.experiments
   config/experiment_a.yaml`, kemudian `python -m src.aggregate` dengan
   `--expect`; periksa konfigurasi yang belum lengkap, `n_energy_clipped`,
   dan outlier.
6. **Eksperimen B (T11).** `python -m src.experiments config/experiment_b.yaml`;
   periksa `n_output_mismatch` (lihat `docs/NOTES.md` §2).
7. **Analisis dan rilis (T12/T13).** Jalankan `src.aggregate` dan `src.plot`,
   isi bagian Hasil di bawah dari `data/processed/summary.csv`, lalu commit
   `data/processed/`, `plots/*.png`, dan `data/manifests/`.

Jalankan semua perintah dari root repo. Model dan commit-nya di-pin di
`config/defaults.yaml`; parameter decoding bersama juga ada di sana. Konfigurasi
yang tidak muat di RAM tidak boleh diganti diam-diam: tambahkan
`skip_reason: "..."` pada entrinya di `config/experiment_a.yaml`.

`--no-power` bisa dipakai untuk menguji pipeline tanpa `sudo`, tetapi run-nya
berstatus `incomplete` dan tidak masuk analisis. Lihat
`python -m src.bench --help` dan `python -m src.experiments --help`.

## Hasil

Belum ada data dari Mac target. Bagian ini diisi dari
`data/processed/summary.csv` setelah Eksperimen A dan B selesai, bersama
spesifikasi mesin dari `data/manifests/environment.md`.

## Keterbatasan

1. `powermetrics` mengukur daya seluruh chip (CPU + GPU + ANE), bukan energi
   proses atau model saja; aktivitas latar belakang ikut terukur.
2. Energi prefill ikut dihitung (`duration_s` mencakup prefill), sedangkan
   `J/token` dibagi jumlah token keluaran saja.
3. Semua angka diukur pada batch size 1.
4. Urutan run, suhu/thermal throttling, aktivitas latar belakang, dan interval
   sampling 100 ms dapat memengaruhi hasil. Idle diukur ulang tiap 10 run dan
   run dengan cakupan sampel daya < 0,9 dikeluarkan dari analisis.
5. Pada speculative decoding, `prompt_tps` mencakup prefill dua model
   sehingga tidak sebanding langsung dengan baseline; bandingkan
   `generation_tps` dan `J/token`.

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
