import json

from src.smoke_check import main
from tests.factories import measured_record


def write(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def test_measured_run_passes(tmp_path, capsys):
    path = write(tmp_path / "s.jsonl", [measured_record(status="warmup", run=-1), measured_record()])
    assert main([str(path)]) == 0
    assert "smoke OK" in capsys.readouterr().out


def test_incomplete_only_fails_with_reason(tmp_path, capsys):
    path = write(tmp_path / "s.jsonl", [
        measured_record(status="incomplete", joules_per_token=None, error="cakupan 0.40 < 0.9"),
    ])
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "tidak ada run measured" in out and "cakupan 0.40" in out


def test_missing_file_fails(tmp_path, capsys):
    assert main([str(tmp_path / "nope.jsonl")]) == 1
    assert "tidak ada" in capsys.readouterr().out


def test_invalid_file_fails(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text("not-json\n")
    assert main([str(path)]) == 1
