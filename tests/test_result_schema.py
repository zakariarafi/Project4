import json

import pytest

from src.schemas import validate_file, validate_record
from tests.factories import measured_record


measured = measured_record


def test_valid_measured_record():
    assert validate_record(measured()) == []


def test_missing_and_unknown_fields():
    record = measured(extra=1)
    del record["seed"]
    errors = validate_record(record)
    assert "field hilang: seed" in errors
    assert "field tidak dikenal: extra" in errors


def test_bool_is_not_accepted_as_int():
    assert validate_record(measured(run=True)) == ["run bertipe bool"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"joules_per_token": None},
        {"generation_tokens": 0},
        {"power_coverage": 0.5},
        {"run": -1},
        {"status": "done"},
        {"draft_model": "mlx-community/Qwen3-0.6B-4bit"},  # tanpa k
        {"draft_fraction": 0.4},  # tanpa draft model
    ],
)
def test_invalid_measured_records(overrides):
    assert validate_record(measured(**overrides))


def test_speculative_record():
    record = measured(
        draft_model="mlx-community/Qwen3-0.6B-4bit", num_draft_tokens=4, draft_fraction=0.6
    )
    assert validate_record(record) == []
    assert validate_record({**record, "draft_fraction": 1.5})


def test_failed_record_requires_error():
    failed = measured(status="failed", generation_tokens=None, joules_per_token=None)
    assert validate_record(failed) == ["record failed wajib menyertakan error/alasan"]
    assert validate_record({**failed, "error": "RuntimeError: OOM"}) == []


def test_warmup_run_number():
    assert validate_record(measured(status="warmup", run=-1)) == []
    assert validate_record(measured(status="warmup", run=0))


def test_validate_file_detects_duplicates_and_bad_json(tmp_path):
    path = tmp_path / "results.jsonl"
    line = json.dumps(measured())
    path.write_text(f"{line}\n{line}\nnot-json\n")
    problems = validate_file(path)
    assert len(problems) == 2
    assert "duplikat" in problems[0]
    assert "JSON tidak valid" in problems[1]
