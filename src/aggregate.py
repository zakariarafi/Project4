"""Agregasi record hasil benchmark menjadi tabel ringkasan.

    python -m src.aggregate data/raw/results.jsonl \\
        --expect config/experiment_a.yaml config/experiment_b.yaml

Hanya record `measured` yang masuk statistik; warm-up, run gagal, dan run
tidak lengkap hanya dihitung. Input yang melanggar skema, berisi run duplikat,
atau mencampur parameter decoding dalam satu experiment ID ditolak tanpa
menulis output apa pun.

Output:
- `data/processed/summary.csv`: satu baris per (experiment_id, config_id)
- `data/processed/results_final.jsonl`: record `measured` yang mendasarinya
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

from src.schemas import validate_file

# Parameter yang wajib sama untuk semua run measured dalam satu experiment ID.
EXPERIMENT_INVARIANTS = (
    "temperature", "seed", "max_tokens", "enable_thinking", "power_interval_ms",
)
# Field yang wajib sama untuk semua record dalam satu konfigurasi.
CONFIG_INVARIANTS = ("model", "draft_model", "num_draft_tokens")

METRICS = (
    "generation_tps",
    "joules_per_token",
    "peak_memory_gb",
    "avg_watts",
    "prompt_tps",
    "duration_s",
    "draft_fraction",
)
STATUSES = ("measured", "failed", "incomplete", "skipped_resource_limit")

MODEL_RE = re.compile(r"-(\d+(?:\.\d+)?)B-(bf16|8bit|4bit)$")

COLUMNS = (
    [
        "experiment_id", "config_id", "model", "model_size_b", "precision",
        "draft_model", "num_draft_tokens", "mode",
        "expected_measured", "n_measured", "n_failed", "n_incomplete", "n_skipped",
        "complete", "n_energy_clipped", "n_output_mismatch",
    ]
    + [f"{m}_{stat}" for m in METRICS for stat in ("mean", "median", "std")]
    + ["speedup_vs_baseline", "energy_ratio_vs_baseline", "notes"]
)


class AggregateError(Exception):
    pass


def parse_model(repo: str | None) -> tuple[float | None, str | None]:
    """`mlx-community/Qwen3-1.7B-4bit` -> (1.7, "4bit")."""
    match = MODEL_RE.search(repo or "")
    return (float(match.group(1)), match.group(2)) if match else (None, None)


def load_records(paths: list[Path]) -> list[dict]:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise AggregateError("file input tidak ada: " + ", ".join(missing))
    problems = [p for path in paths for p in validate_file(path)]
    if problems:
        raise AggregateError("input tidak valid:\n  " + "\n  ".join(problems))
    records = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    return records


def check_consistency(records: list[dict]) -> list[str]:
    problems = []
    by_experiment: dict[str, dict[str, set]] = {}
    by_config: dict[tuple, dict[str, set]] = {}
    for record in records:
        if record["status"] == "measured":
            values = by_experiment.setdefault(record["experiment_id"], {})
            for field in EXPERIMENT_INVARIANTS:
                values.setdefault(field, set()).add(record[field])
        if record["status"] != "warmup":
            key = (record["experiment_id"], record["config_id"])
            values = by_config.setdefault(key, {})
            for field in CONFIG_INVARIANTS:
                values.setdefault(field, set()).add(record[field])
    for experiment_id, fields in by_experiment.items():
        for field, seen in fields.items():
            if len(seen) > 1:
                problems.append(f"{experiment_id}: `{field}` bercampur {sorted(map(str, seen))}")
    for (experiment_id, config_id), fields in by_config.items():
        for field, seen in fields.items():
            if len(seen) > 1:
                problems.append(
                    f"{experiment_id}/{config_id}: `{field}` bercampur {sorted(map(str, seen))}"
                )
    return problems


def expected_from_configs(paths: list[Path], defaults: Path | None = None) -> dict:
    """(experiment_id, config_id) -> rencana: jumlah run measured dan model."""
    from src.bench import load_prompts
    from src.experiments import DEFAULTS_PATH, load_experiment

    expected = {}
    for path in paths:
        for spec in load_experiment(path, defaults or DEFAULTS_PATH):
            key = (spec["experiment_id"], spec["config_id"])
            plan = {
                "model": spec["model"]["repo"],
                "draft_model": spec["draft_model"]["repo"] if spec["draft_model"] else None,
                "num_draft_tokens": spec["num_draft_tokens"],
                "expected": 0,
            }
            if not spec["skip_reason"]:
                params = spec["params"]
                prompts = load_prompts(Path(params["prompts"]), params.get("limit_prompts"))
                plan["expected"] = params["runs"] * len(prompts)
            expected[key] = plan
    return expected


def _stats(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    std = statistics.stdev(values) if len(values) > 1 else None
    return statistics.fmean(values), statistics.median(values), std


def summarize(records: list[dict], expected: dict | None = None) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for key in expected or {}:
        groups[key] = []
    for record in records:
        if record["status"] != "warmup":
            groups.setdefault((record["experiment_id"], record["config_id"]), []).append(record)

    rows = []
    for (experiment_id, config_id), group in groups.items():
        measured = [r for r in group if r["status"] == "measured"]
        counts = {s: sum(r["status"] == s for r in group) for s in STATUSES}
        plan = (expected or {}).get((experiment_id, config_id))
        sample = group[0] if group else plan or {}
        size, precision = parse_model(sample.get("model"))
        draft = sample.get("draft_model")
        row = {
            "experiment_id": experiment_id,
            "config_id": config_id,
            "model": sample.get("model"),
            "model_size_b": size,
            "precision": precision,
            "draft_model": draft,
            "num_draft_tokens": sample.get("num_draft_tokens"),
            "mode": "speculative" if draft else "baseline",
            "expected_measured": plan["expected"] if plan else None,
            "n_measured": counts["measured"],
            "n_failed": counts["failed"],
            "n_incomplete": counts["incomplete"],
            "n_skipped": counts["skipped_resource_limit"],
            "n_energy_clipped": sum(bool(r["energy_clipped"]) for r in measured),
            "n_output_mismatch": None,
            "speedup_vs_baseline": None,
            "energy_ratio_vs_baseline": None,
        }
        for metric in METRICS:
            values = [r[metric] for r in measured if r[metric] is not None]
            mean, median, std = _stats(values)
            row[f"{metric}_mean"], row[f"{metric}_median"], row[f"{metric}_std"] = mean, median, std

        if row["expected_measured"] is None:
            row["complete"] = None
        else:
            row["complete"] = (
                counts["skipped_resource_limit"] > 0
                if row["expected_measured"] == 0
                else counts["measured"] >= row["expected_measured"]
            )
        notes = sorted({r["error"] for r in group if r["status"] != "measured" and r["error"]})
        if not group:
            notes = ["belum dijalankan"]
        row["notes"] = "; ".join(note[:120] for note in notes) or None
        row["_measured"] = measured
        rows.append(row)

    _link_baselines(rows)
    for row in rows:
        del row["_measured"]
    return rows


def _link_baselines(rows: list[dict]) -> None:
    """Bandingkan run speculative dengan baseline target yang sama (experiment ID sama)."""
    baselines = {
        (r["experiment_id"], r["model"]): r for r in rows if r["mode"] == "baseline"
    }
    for row in rows:
        if row["mode"] != "speculative":
            continue
        base = baselines.get((row["experiment_id"], row["model"]))
        if base is None:
            continue
        if row["generation_tps_mean"] and base["generation_tps_mean"]:
            row["speedup_vs_baseline"] = row["generation_tps_mean"] / base["generation_tps_mean"]
        if row["joules_per_token_mean"] is not None and base["joules_per_token_mean"]:
            row["energy_ratio_vs_baseline"] = (
                row["joules_per_token_mean"] / base["joules_per_token_mean"]
            )
        # Temperature 0: teks speculative harus sama dengan baseline per prompt.
        hashes: dict[str, set] = {}
        for record in base["_measured"]:
            hashes.setdefault(record["prompt_id"], set()).add(record["output_sha256"])
        compared = [r for r in row["_measured"] if r["prompt_id"] in hashes]
        if compared:
            row["n_output_mismatch"] = sum(
                r["output_sha256"] not in hashes[r["prompt_id"]] for r in compared
            )


def _format(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def write_summary(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([_format(row[column]) for column in COLUMNS])


def write_final(records: list[dict], rows: list[dict], path: Path) -> None:
    order = {(r["experiment_id"], r["config_id"]): i for i, r in enumerate(rows)}
    measured = sorted(
        (r for r in records if r["status"] == "measured"),
        key=lambda r: (order[(r["experiment_id"], r["config_id"])], r["prompt_id"], r["run"]),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in measured:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.aggregate",
        description="Buat summary.csv dan results_final.jsonl dari record hasil.",
    )
    p.add_argument("inputs", nargs="*", type=Path, default=[Path("data/raw/results.jsonl")])
    p.add_argument(
        "--expect", nargs="+", type=Path, default=[], metavar="CONFIG.yaml",
        help="config eksperimen untuk audit kelengkapan matriks",
    )
    p.add_argument("--defaults", type=Path, help="default: config/defaults.yaml")
    p.add_argument("--summary", type=Path, default=Path("data/processed/summary.csv"))
    p.add_argument("--final", type=Path, default=Path("data/processed/results_final.jsonl"))
    args = p.parse_args(argv)

    try:
        records = load_records(args.inputs)
        problems = check_consistency(records)
        if problems:
            raise AggregateError("parameter tidak konsisten:\n  " + "\n  ".join(problems))
    except AggregateError as exc:
        print(exc, file=sys.stderr)
        return 1

    expected = expected_from_configs(args.expect, args.defaults) if args.expect else None
    rows = summarize(records, expected)
    write_summary(rows, args.summary)
    write_final(records, rows, args.final)

    for row in rows:
        target = row["expected_measured"]
        progress = f"{row['n_measured']}/{target}" if target is not None else row["n_measured"]
        print(
            f"{row['experiment_id']}/{row['config_id']}: measured={progress} "
            f"failed={row['n_failed']} incomplete={row['n_incomplete']} "
            f"skipped={row['n_skipped']} tps={_format(row['generation_tps_mean'])} "
            f"J/tok={_format(row['joules_per_token_mean'])}"
        )
    incomplete = [r["config_id"] for r in rows if r["complete"] is False]
    mismatched = [r["config_id"] for r in rows if r["n_output_mismatch"]]
    if incomplete:
        print("belum lengkap: " + ", ".join(incomplete))
    if mismatched:
        print("output speculative berbeda dari baseline: " + ", ".join(mismatched))
    print(f"ditulis: {args.summary}, {args.final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
