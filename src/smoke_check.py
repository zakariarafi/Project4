"""Periksa hasil smoke run sebelum eksperimen penuh dijalankan.

    python -m src.smoke_check data/raw/smoke.jsonl

Lulus bila file valid menurut skema dan berisi minimal satu run `measured`
(artinya generasi berhasil dan sampel daya menutup jendela run).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.schemas import validate_file


def check(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path} tidak ada: bench berhenti sebelum menulis record (lihat error di atas)"]
    problems = validate_file(path)
    if problems:
        return problems
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not any(r["status"] == "measured" for r in records):
        reasons = [f"{r['status']}: {r['error']}" for r in records if r["status"] != "warmup"]
        return ["tidak ada run measured"] + reasons
    return []


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("pemakaian: python -m src.smoke_check FILE.jsonl", file=sys.stderr)
        return 2
    path = Path(args[0])
    problems = check(path)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line) if line.strip() else {}
        if record.get("status") != "measured":
            continue
        print(
            f"smoke OK {record['config_id']} {record['prompt_id']}: "
            f"{record['generation_tps']:.1f} token/s, {record['joules_per_token']:.4f} J/token, "
            f"daya {record['avg_watts']:.1f} W (idle {record['idle_watts']:.1f} W), "
            f"cakupan {record['power_coverage']:.2f} dari {record['power_samples']} sampel"
            + (", energy_clipped" if record["energy_clipped"] else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
