"""Skema record hasil benchmark dan validatornya.

Satu baris JSONL = satu record. Validator sengaja tidak memakai dependensi
eksternal agar bisa dijalankan di mana saja:

    python -m src.schemas data/raw/results.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1

STATUSES = {"measured", "warmup", "failed", "incomplete", "skipped_resource_limit"}

# Porsi durasi run yang wajib tertutup sampel daya agar run boleh `measured`.
MIN_POWER_COVERAGE = 0.9

# Nomor run khusus untuk record yang bukan pengulangan terukur.
WARMUP_RUN = -1

_STR = (str,)
_INT = (int,)
_FLOAT = (int, float)
_BOOL = (bool,)

# nama field -> (tipe yang diterima, boleh null)
FIELDS: dict[str, tuple[tuple[type, ...], bool]] = {
    "schema_version": (_INT, False),
    "experiment_id": (_STR, False),
    "config_id": (_STR, False),
    "model": (_STR, False),
    "draft_model": (_STR, True),
    "num_draft_tokens": (_INT, True),
    "prompt_id": (_STR, False),
    "run": (_INT, False),
    "status": (_STR, False),
    # parameter decoding (FR-04)
    "temperature": (_FLOAT, False),
    "seed": (_INT, False),
    "max_tokens": (_INT, False),
    "enable_thinking": (_BOOL, False),
    # metrik generasi; null jika run gagal
    "generation_tokens": (_INT, True),
    "generation_tps": (_FLOAT, True),
    "prompt_tokens": (_INT, True),
    "prompt_tps": (_FLOAT, True),
    "peak_memory_gb": (_FLOAT, True),
    "duration_s": (_FLOAT, True),
    # energi; lihat docs/PRD.md §7
    "idle_watts": (_FLOAT, True),
    "avg_watts": (_FLOAT, True),
    "joules_per_token": (_FLOAT, True),
    "energy_clipped": (_BOOL, True),
    "power_interval_ms": (_INT, True),
    "power_samples": (_INT, True),
    "power_coverage": (_FLOAT, True),
    # speculative decoding dan pemeriksaan kesetaraan output
    "draft_fraction": (_FLOAT, True),
    "output_sha256": (_STR, True),
    "started_at": (_STR, False),
    "finished_at": (_STR, True),
    "error": (_STR, True),
}

# Field yang wajib terisi (bukan null) pada record `measured`.
MEASURED_REQUIRED = (
    "generation_tokens",
    "generation_tps",
    "prompt_tokens",
    "peak_memory_gb",
    "duration_s",
    "idle_watts",
    "avg_watts",
    "joules_per_token",
    "energy_clipped",
    "power_interval_ms",
    "power_samples",
    "power_coverage",
    "output_sha256",
    "finished_at",
)


def record_key(record: dict) -> tuple:
    """Kunci unik satu run terukur (FR-11)."""
    return (
        record["experiment_id"],
        record["config_id"],
        record["prompt_id"],
        record["run"],
    )


def _type_ok(value, types: tuple[type, ...]) -> bool:
    # bool adalah subclass int; jangan terima True/False sebagai angka.
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def validate_record(record: dict) -> list[str]:
    """Kembalikan daftar pelanggaran skema; list kosong berarti valid."""
    errors: list[str] = []

    missing = [name for name in FIELDS if name not in record]
    errors.extend(f"field hilang: {name}" for name in missing)
    unknown = sorted(set(record) - set(FIELDS))
    errors.extend(f"field tidak dikenal: {name}" for name in unknown)

    for name, (types, nullable) in FIELDS.items():
        if name not in record:
            continue
        value = record[name]
        if value is None:
            if not nullable:
                errors.append(f"{name} tidak boleh null")
        elif not _type_ok(value, types):
            errors.append(f"{name} bertipe {type(value).__name__}")
    if errors:
        return errors

    if record["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version {record['schema_version']} != {SCHEMA_VERSION}")
    status = record["status"]
    if status not in STATUSES:
        errors.append(f"status tidak dikenal: {status}")

    if (record["draft_model"] is None) != (record["num_draft_tokens"] is None):
        errors.append("draft_model dan num_draft_tokens harus diisi bersama")
    if record["num_draft_tokens"] is not None and record["num_draft_tokens"] <= 0:
        errors.append("num_draft_tokens harus > 0")
    if record["draft_model"] is None and record["draft_fraction"] is not None:
        errors.append("draft_fraction hanya untuk run speculative")
    fraction = record["draft_fraction"]
    if fraction is not None and not 0.0 <= fraction <= 1.0:
        errors.append("draft_fraction harus di rentang [0, 1]")

    if status == "measured":
        if record["run"] < 0:
            errors.append("run measured harus >= 0")
        errors.extend(
            f"{name} wajib terisi pada record measured"
            for name in MEASURED_REQUIRED
            if record[name] is None
        )
        if errors:
            return errors
        if record["generation_tokens"] <= 0:
            errors.append("generation_tokens harus > 0")
        if record["duration_s"] <= 0:
            errors.append("duration_s harus > 0")
        if record["generation_tps"] <= 0:
            errors.append("generation_tps harus > 0")
        if record["joules_per_token"] < 0:
            errors.append("joules_per_token tidak boleh negatif")
        if record["power_coverage"] < MIN_POWER_COVERAGE:
            errors.append(f"power_coverage < {MIN_POWER_COVERAGE}")
    elif status == "warmup":
        if record["run"] != WARMUP_RUN:
            errors.append(f"run warmup harus {WARMUP_RUN}")
    elif status in ("failed", "incomplete", "skipped_resource_limit"):
        if not record["error"]:
            errors.append(f"record {status} wajib menyertakan error/alasan")

    return errors


def validate_file(path: Path) -> list[str]:
    """Validasi seluruh JSONL, termasuk duplikasi kunci run `measured`."""
    problems: list[str] = []
    seen: dict[tuple, int] = {}
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path}:{lineno}: JSON tidak valid ({exc})")
                continue
            if not isinstance(record, dict):
                problems.append(f"{path}:{lineno}: baris bukan objek JSON")
                continue
            for error in validate_record(record):
                problems.append(f"{path}:{lineno}: {error}")
            if record.get("status") == "measured" and all(
                k in record for k in ("experiment_id", "config_id", "prompt_id", "run")
            ):
                key = record_key(record)
                if key in seen:
                    problems.append(
                        f"{path}:{lineno}: duplikat run measured {key} (baris {seen[key]})"
                    )
                else:
                    seen[key] = lineno
    return problems


def main(argv: list[str] | None = None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print("pemakaian: python -m src.schemas FILE.jsonl [...]", file=sys.stderr)
        return 2
    problems = [p for path in paths for p in validate_file(path)]
    for problem in problems:
        print(problem)
    print(f"{len(problems)} masalah ditemukan")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
