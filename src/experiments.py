"""Jalankan satu matriks eksperimen dari file YAML di config/.

    python -m src.experiments config/experiment_a.yaml --dry-run
    sudo -v && python -m src.experiments config/experiment_a.yaml
    python -m src.experiments config/experiment_b.yaml --only qwen3-4b-4bit-k4

Setiap entri `configs` diterjemahkan menjadi satu pemanggilan `src.bench`.
Urutan prioritas parameter: config/defaults.yaml < `params` di file
eksperimen < entri konfigurasi. Karena bench melewati run yang sudah
`measured`, perintah yang sama aman dijalankan ulang setelah terhenti.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

import yaml

DEFAULTS_PATH = Path("config/defaults.yaml")

# Parameter yang boleh diatur di YAML; nama = opsi CLI bench tanpa `--`.
PARAMS = {
    "prompts": str,
    "limit_prompts": int,
    "runs": int,
    "max_tokens": int,
    "temperature": float,
    "seed": int,
    "enable_thinking": bool,
    "warmup_tokens": int,
    "output": str,
    "manifest_dir": str,
    "power_interval_ms": int,
    "idle_seconds": float,
    "reidle_every": int,
    "reidle_seconds": float,
}
CONFIG_KEYS = {"config_id", "model", "draft_model", "num_draft_tokens", "skip_reason"}
MODEL_KEYS = {"repo", "revision", "size_gb"}


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: isi harus berupa mapping")
    return data


def _check_params(params: dict, where: str) -> None:
    for key, value in params.items():
        if key not in PARAMS:
            raise ValueError(f"{where}: parameter tidak dikenal `{key}`")
        expected = PARAMS[key]
        ok = isinstance(value, expected) and not (
            isinstance(value, bool) and expected is not bool
        )
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            ok = True
        if not ok:
            raise ValueError(f"{where}: `{key}` harus bertipe {expected.__name__}")


def load_experiment(path: Path, defaults_path: Path = DEFAULTS_PATH) -> list[dict]:
    """Kembalikan daftar spesifikasi lengkap per konfigurasi, sudah divalidasi."""
    defaults = _load_yaml(defaults_path)
    experiment = _load_yaml(path)

    models = defaults.get("models") or {}
    for alias, model in models.items():
        unknown = set(model) - MODEL_KEYS
        if unknown or "repo" not in model:
            raise ValueError(f"{defaults_path}: model `{alias}` tidak valid ({sorted(unknown)})")

    base = dict(defaults.get("params") or {})
    _check_params(base, str(defaults_path))
    overrides = experiment.get("params") or {}
    _check_params(overrides, str(path))
    base.update(overrides)

    experiment_id = experiment.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise ValueError(f"{path}: `experiment_id` wajib diisi")
    configs = experiment.get("configs") or []
    if not configs:
        raise ValueError(f"{path}: `configs` kosong")

    specs = []
    seen = set()
    for index, entry in enumerate(configs):
        where = f"{path}: configs[{index}]"
        config_params = {k: v for k, v in entry.items() if k not in CONFIG_KEYS}
        _check_params(config_params, where)
        config_id = entry.get("config_id")
        if not config_id:
            raise ValueError(f"{where}: `config_id` wajib diisi")
        if config_id in seen:
            raise ValueError(f"{where}: config_id duplikat `{config_id}`")
        seen.add(config_id)

        for role in ("model", "draft_model"):
            alias = entry.get(role)
            if alias is not None and alias not in models:
                raise ValueError(f"{where}: {role} `{alias}` tidak ada di registry model")
        if entry.get("model") is None:
            raise ValueError(f"{where}: `model` wajib diisi")
        if (entry.get("draft_model") is None) != (entry.get("num_draft_tokens") is None):
            raise ValueError(f"{where}: draft_model dan num_draft_tokens harus diisi bersama")

        specs.append(
            {
                "experiment_id": experiment_id,
                "config_id": config_id,
                "model": models[entry["model"]],
                "draft_model": models[entry["draft_model"]] if entry.get("draft_model") else None,
                "num_draft_tokens": entry.get("num_draft_tokens"),
                "skip_reason": entry.get("skip_reason"),
                "params": {**base, **config_params},
            }
        )
    return specs


def spec_to_argv(spec: dict) -> list[str]:
    """Terjemahkan satu spesifikasi menjadi argumen CLI `src.bench`."""
    argv = [
        "--experiment-id", spec["experiment_id"],
        "--config-id", spec["config_id"],
        "--model", spec["model"]["repo"],
    ]
    if spec["model"].get("revision"):
        argv += ["--revision", spec["model"]["revision"]]
    if spec["draft_model"]:
        argv += [
            "--draft-model", spec["draft_model"]["repo"],
            "--num-draft-tokens", str(spec["num_draft_tokens"]),
        ]
        if spec["draft_model"].get("revision"):
            argv += ["--draft-revision", spec["draft_model"]["revision"]]
    for key, value in spec["params"].items():
        flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                argv.append(flag)
        else:
            argv += [flag, str(value)]
    if spec["skip_reason"]:
        argv += ["--skip-reason", spec["skip_reason"]]
    return argv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.experiments",
        description="Jalankan semua konfigurasi dalam satu file eksperimen YAML.",
    )
    p.add_argument("experiment", type=Path, help="mis. config/experiment_a.yaml")
    p.add_argument("--defaults", type=Path, default=DEFAULTS_PATH)
    p.add_argument("--only", nargs="+", metavar="CONFIG_ID", help="jalankan sebagian saja")
    p.add_argument("--dry-run", action="store_true", help="cetak perintah bench saja")
    args = p.parse_args(argv)

    specs = load_experiment(args.experiment, args.defaults)
    if args.only:
        unknown = set(args.only) - {s["config_id"] for s in specs}
        if unknown:
            p.error(f"config_id tidak ada: {', '.join(sorted(unknown))}")
        specs = [s for s in specs if s["config_id"] in args.only]

    if args.dry_run:
        for spec in specs:
            print(shlex.join(["python", "-m", "src.bench", *spec_to_argv(spec)]))
        return 0

    from src import bench

    failed = []
    for number, spec in enumerate(specs, start=1):
        print(f"=== [{number}/{len(specs)}] {spec['config_id']} ===", flush=True)
        try:
            code = bench.main(spec_to_argv(spec))
        except Exception as exc:  # satu konfigurasi gagal tidak menghentikan matriks
            print(f"{spec['config_id']} gagal: {type(exc).__name__}: {exc}", flush=True)
            code = 1
        if code:
            failed.append(spec["config_id"])
    print(f"selesai: {len(specs) - len(failed)}/{len(specs)} konfigurasi tanpa run gagal")
    if failed:
        print("perlu dicek: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
