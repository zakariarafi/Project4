import json

import pytest

from src.bench import apply_power, base_record, load_prompts, parse_args, plan_runs
from src.power import WindowPower
from src.schemas import validate_record

ARGS = ["--experiment-id", "smoke", "--config-id", "c", "--model", "m"]


def test_parse_args_requires_draft_pair():
    with pytest.raises(SystemExit):
        parse_args(ARGS + ["--draft-model", "d"])
    args = parse_args(ARGS + ["--draft-model", "d", "--num-draft-tokens", "4"])
    assert args.num_draft_tokens == 4


def test_load_prompts_validates_ids(tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text('{"id": "a", "prompt": "x"}\n{"id": "b", "prompt": "y"}\n')
    assert [p["id"] for p in load_prompts(path)] == ["a", "b"]
    assert [p["id"] for p in load_prompts(path, limit=1)] == ["a"]
    path.write_text('{"id": "a", "prompt": "x"}\n{"id": "a", "prompt": "y"}\n')
    with pytest.raises(ValueError, match="duplikat"):
        load_prompts(path)


def test_plan_skips_measured_and_interleaves_runs():
    args = parse_args(ARGS + ["--runs", "2"])
    prompts = [{"id": "a"}, {"id": "b"}]
    plan = plan_runs(args, prompts, done={("smoke", "c", "a", 0)})
    assert [(run, p["id"]) for run, p in plan] == [(0, "b"), (1, "a"), (1, "b")]


def generated_record(args):
    record = base_record(args, "a", 0, "failed")
    record.update(
        generation_tokens=100, generation_tps=50.0, prompt_tokens=10, prompt_tps=500.0,
        peak_memory_gb=1.0, duration_s=2.0, output_sha256="0" * 64,
        finished_at=record["started_at"],
    )
    return record


def test_apply_power_measured():
    args = parse_args(ARGS)
    record = generated_record(args)
    apply_power(record, WindowPower(7.0, 2.0, 1.0, 20), idle_watts=2.0)
    assert record["status"] == "measured"
    assert record["joules_per_token"] == pytest.approx(0.1)
    assert validate_record(record) == []


@pytest.mark.parametrize(
    "window,idle", [(None, 2.0), (WindowPower(7.0, 1.0, 0.5, 5), 2.0), (None, None)]
)
def test_apply_power_incomplete(window, idle):
    args = parse_args(ARGS + (["--no-power"] if idle is None else []))
    record = generated_record(args)
    apply_power(record, window, idle)
    assert record["status"] == "incomplete"
    assert record["joules_per_token"] is None
    assert validate_record(record) == []


def test_skip_reason_writes_valid_record(tmp_path):
    from src.bench import main

    out = tmp_path / "r.jsonl"
    assert main(ARGS + ["--skip-reason", "RAM 16 GB tidak cukup", "--output", str(out)]) == 0
    record = json.loads(out.read_text())
    assert record["status"] == "skipped_resource_limit"
    assert validate_record(record) == []
