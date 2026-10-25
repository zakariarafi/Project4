#!/usr/bin/env bash
# Seluruh pengumpulan data di Mac Apple Silicon (README, "Urutan kerja di Mac").
#
#   bash scripts/run_mac.sh          # langkah 1-7: lingkungan sampai grafik
#   bash scripts/run_mac.sh smoke    # berhenti setelah smoke run (langkah 1-4)
#
# Aman dijalankan ulang: run yang sudah `measured` dilewati. Jalankan dari
# Terminal (bukan lewat SSH tanpa TTY) karena `sudo -v` meminta password sekali.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=${1:-all}
PY=${PYTHON:-python3.12}

step() { printf '\n=== %s ===\n' "$*"; }
die() { printf '\nBERHENTI: %s\n' "$*" >&2; exit 1; }

[[ "$MODE" == all || "$MODE" == smoke ]] || die "argumen harus 'all' atau 'smoke'"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || die "butuh macOS di Apple Silicon"
command -v "$PY" >/dev/null || die "$PY tidak ditemukan (mis. brew install python@3.12)"

step "1. Lingkungan (T01)"
[[ -d .venv ]] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
mkdir -p data/manifests data/raw
{
    echo '# Environment'
    echo
    echo '```'
    sw_vers
    sysctl -n machdep.cpu.brand_string
    echo "RAM bytes: $(sysctl -n hw.memsize)"
    df -h .
    pmset -g batt | head -1
    python --version
    pip show mlx mlx-lm | grep -E '^(Name|Version)'
    echo "git: $(git rev-parse HEAD 2>/dev/null || echo 'bukan clone git')"
    echo '```'
} > data/manifests/environment.md
cat data/manifests/environment.md

step "2. Kapasitas (T02)"
free_gb=$(df -g . | awk 'NR==2 {print $4}')
ram_gb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
echo "RAM ${ram_gb} GB, disk kosong ${free_gb} GB (unduhan model ±23 GB)"
(( free_gb >= 30 )) || die "disk kosong ${free_gb} GB < 30 GB"
if (( ram_gb < 16 )); then
    echo "PERINGATAN: RAM < 16 GB. Jika Qwen3-4B bf16 gagal dimuat, isi skip_reason"
    echo "di config/experiment_a.yaml dan terapkan D-004 (docs/DECISIONS.md)."
fi
pmset -g batt | grep -q "AC Power" || echo "PERINGATAN: tidak tersambung ke charger; mode daya baterai mengubah hasil."

step "3. powermetrics (T04)"
sudo -v
# bench memanggil `sudo -n powermetrics` di awal setiap konfigurasi, dan satu
# konfigurasi bisa lebih lama dari timeout sudo (default 5 menit). Segarkan
# izin sudo setiap menit selama script ini berjalan.
( while kill -0 "$$" 2>/dev/null; do sudo -n true; sleep 60; done ) &
keepalive=$!
# Cegah Mac tidur selama eksperimen yang bisa berjam-jam.
caffeinate -dimsu -w "$$" &
trap 'kill "$keepalive" 2>/dev/null || true' EXIT
fixture="tests/fixtures/powermetrics_macos$(sw_vers -productVersion).txt"
# Redirect sengaja di luar sudo: file ditulis sebagai user agar bisa di-commit.
# shellcheck disable=SC2024
sudo -n powermetrics --samplers cpu_power,gpu_power -i 100 -n 5 > "$fixture"
echo "contoh output: $fixture"
python -m pytest -q

step "4. Smoke run (T07/T08)"
smoke=data/raw/smoke.jsonl
rm -f "$smoke"
revision=$(python -c "import yaml; print(yaml.safe_load(open('config/defaults.yaml'))['models']['qwen3-0.6b-4bit']['revision'])")
python -m src.bench --experiment-id smoke --config-id qwen3-0.6b-4bit \
    --model mlx-community/Qwen3-0.6B-4bit --revision "$revision" \
    --limit-prompts 1 --runs 1 --output "$smoke" || true
python -m src.smoke_check "$smoke" || die "smoke run belum measured; perbaiki sebelum lanjut"
[[ "$MODE" == smoke ]] && exit 0

step "5. Eksperimen A (T09)"
python -m src.experiments config/experiment_a.yaml || echo "ada konfigurasi A yang belum berhasil; lihat ringkasan."
python -m src.aggregate data/raw/results.jsonl --expect config/experiment_a.yaml

step "6. Eksperimen B (T11)"
python -m src.experiments config/experiment_b.yaml || echo "ada konfigurasi B yang belum berhasil; lihat ringkasan."

step "7. Agregasi dan grafik (T10/T12)"
python -m src.aggregate data/raw/results.jsonl \
    --expect config/experiment_a.yaml config/experiment_b.yaml
python -m src.plot

cat <<'EOF'

Selesai. Periksa sebelum commit:
- konfigurasi "belum lengkap" dan "output speculative berbeda" di ringkasan atas
  (docs/NOTES.md §2, docs/EXPERIMENT_PLAN.md);
- isi bagian Hasil di README dari data/processed/summary.csv;
- git add data/processed data/manifests plots tests/fixtures README.md
EOF
