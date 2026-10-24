import csv
import json
from pathlib import Path

import pytest

from src.aggregate import (
    AggregateError, check_consistency, expected_from_configs, load_records, main,
    parse_model, summarize,
)
from tests.factories import measured_record

ROOT = Path(__file__).resolve().parent.parent
DRAFT = "mlx-community/Qwen3-0.6B-4bit"
TARGET = "mlx-community/Qwen3-4B-4bit"


def b_record(config_id, prompt, run, tps, jpt, sha, k=None):
    return measured_record(
        experiment_id="B-speculative", config_id=config_id, model=TARGET,
        draft_model=DRAFT if k else None, num_draft_tokens=k,
        draft_fraction=0.5 if k else None, prompt_id=prompt, run=run,
        generation_tps=tps, joules_per_token=jpt, output_sha256=sha,
    )


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def test_parse_model():
    assert parse_model("mlx-community/Qwen3-1.7B-4bit") == (1.7, "4bit")
    assert parse_model("mlx-community/Qwen3-0.6B-bf16") == (0.6, "bf16")
    assert parse_model("other/model") == (None, None)


def test_summary_stats_and_status_counts():
    records = [
        measured_record(run=0, generation_tps=100.0, joules_per_token=0.1),
        measured_record(run=1, generation_tps=110.0, joules_per_token=0.3, energy_clipped=True),
        measured_record(run=2, generation_tps=120.0, joules_per_token=0.2),
        measured_record(status="warmup", run=-1),
        measured_record(status="failed", run=3, error="RuntimeError: x"),
        measured_record(status="incomplete", run=4, error="cakupan 0.50 < 0.9"),
    ]
    (row,) = summarize(records)
    assert (row["n_measured"], row["n_failed"], row["n_incomplete"]) == (3, 1, 1)
    assert row["generation_tps_mean"] == pytest.approx(110.0)
    assert row["generation_tps_median"] == pytest.approx(110.0)
    assert row["generation_tps_std"] == pytest.approx(10.0)
    assert row["joules_per_token_median"] == pytest.approx(0.2)
    assert row["n_energy_clipped"] == 1
    assert row["draft_fraction_mean"] is None
    assert (row["model_size_b"], row["precision"], row["mode"]) == (0.6, "4bit", "baseline")
    assert "RuntimeError: x" in row["notes"]


def test_single_run_has_no_std():
    (row,) = summarize([measured_record()])
    assert row["generation_tps_std"] is None


def test_speculative_compared_with_baseline():
    records = [
        b_record("base", "p1", 0, 50.0, 0.4, "a" * 64),
        b_record("base", "p2", 0, 50.0, 0.4, "b" * 64),
        b_record("k4", "p1", 0, 75.0, 0.3, "a" * 64, k=4),
        b_record("k4", "p2", 0, 75.0, 0.3, "c" * 64, k=4),  # beda dari baseline
    ]
    base, spec = summarize(records)
    assert base["mode"] == "baseline" and spec["mode"] == "speculative"
    assert spec["speedup_vs_baseline"] == pytest.approx(1.5)
    assert spec["energy_ratio_vs_baseline"] == pytest.approx(0.75)
    assert spec["n_output_mismatch"] == 1
    assert spec["draft_fraction_mean"] == pytest.approx(0.5)
    assert base["n_output_mismatch"] is None


def test_mixed_parameters_are_rejected():
    records = [measured_record(run=0), measured_record(run=1, max_tokens=128)]
    assert any("max_tokens" in p for p in check_consistency(records))
    records = [measured_record(run=0), measured_record(run=1, model="other/m")]
    assert any("model" in p for p in check_consistency(records))


def test_invalid_input_is_rejected(tmp_path):
    path = write_jsonl(tmp_path / "r.jsonl", [measured_record(), measured_record()])
    with pytest.raises(AggregateError, match="duplikat"):
        load_records([path])


def test_expected_matrix_from_configs():
    expected = expected_from_configs(
        [ROOT / "config" / "experiment_a.yaml", ROOT / "config" / "experiment_b.yaml"],
        ROOT / "config" / "defaults.yaml",
    )
    assert len(expected) == 17
    assert all(plan["expected"] == 30 for plan in expected.values())
    assert expected[("B-speculative", "qwen3-4b-4bit-k8")]["num_draft_tokens"] == 8


def test_missing_and_skipped_configs_are_reported():
    expected = {
        ("A-size-precision", "qwen3-0.6b-4bit"): {
            "model": "mlx-community/Qwen3-0.6B-4bit", "draft_model": None,
            "num_draft_tokens": None, "expected": 2,
        },
        ("A-size-precision", "qwen3-4b-bf16"): {
            "model": "mlx-community/Qwen3-4B-bf16", "draft_model": None,
            "num_draft_tokens": None, "expected": 0,
        },
        ("A-size-precision", "qwen3-1.7b-8bit"): {
            "model": "mlx-community/Qwen3-1.7B-8bit", "draft_model": None,
            "num_draft_tokens": None, "expected": 2,
        },
    }
    skipped = measured_record(
        config_id="qwen3-4b-bf16", model="mlx-community/Qwen3-4B-bf16",
        status="skipped_resource_limit", prompt_id="*", run=-1, error="RAM 16 GB",
    )
    records = [measured_record(run=0), measured_record(run=1), skipped]
    rows = {r["config_id"]: r for r in summarize(records, expected)}
    assert rows["qwen3-0.6b-4bit"]["complete"] is True
    assert rows["qwen3-4b-bf16"]["complete"] is True
    assert rows["qwen3-4b-bf16"]["notes"] == "RAM 16 GB"
    missing = rows["qwen3-1.7b-8bit"]
    assert missing["complete"] is False and missing["n_measured"] == 0
    assert (missing["model_size_b"], missing["precision"]) == (1.7, "8bit")
    assert missing["notes"] == "belum dijalankan"


def test_main_writes_outputs(tmp_path):
    records = [
        measured_record(run=0),
        measured_record(status="warmup", run=-1),
        measured_record(config_id="qwen3-0.6b-8bit", model="mlx-community/Qwen3-0.6B-8bit"),
    ]
    raw = write_jsonl(tmp_path / "results.jsonl", records)
    summary, final = tmp_path / "summary.csv", tmp_path / "final.jsonl"
    assert main([str(raw), "--summary", str(summary), "--final", str(final)]) == 0
    rows = list(csv.DictReader(summary.open()))
    assert [r["config_id"] for r in rows] == ["qwen3-0.6b-4bit", "qwen3-0.6b-8bit"]
    assert rows[0]["generation_tps_mean"] == "180.5"
    assert rows[0]["complete"] == ""
    final_records = [json.loads(line) for line in final.read_text().splitlines()]
    assert len(final_records) == 2
    assert all(r["status"] == "measured" for r in final_records)


def test_main_refuses_inconsistent_data(tmp_path, capsys):
    raw = write_jsonl(
        tmp_path / "r.jsonl", [measured_record(run=0), measured_record(run=1, seed=1)]
    )
    summary = tmp_path / "summary.csv"
    assert main([str(raw), "--summary", str(summary), "--final", str(tmp_path / "f")]) == 1
    assert not summary.exists()
    assert "seed" in capsys.readouterr().err
