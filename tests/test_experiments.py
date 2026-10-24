import re
from pathlib import Path

import pytest
import yaml

from src.bench import parse_args
from src.experiments import load_experiment, main, spec_to_argv

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = ROOT / "config" / "defaults.yaml"
EXP_A = ROOT / "config" / "experiment_a.yaml"
EXP_B = ROOT / "config" / "experiment_b.yaml"


def test_experiment_a_matrix():
    specs = load_experiment(EXP_A, DEFAULTS)
    assert len(specs) == 9
    repos = {s["model"]["repo"] for s in specs}
    assert repos == {
        f"mlx-community/Qwen3-{size}-{precision}"
        for size in ("0.6B", "1.7B", "4B")
        for precision in ("bf16", "8bit", "4bit")
    }
    assert all(s["draft_model"] is None for s in specs)


def test_experiment_b_matrix():
    specs = load_experiment(EXP_B, DEFAULTS)
    assert len(specs) == 8
    for target in ("Qwen3-4B-bf16", "Qwen3-4B-4bit"):
        group = [s for s in specs if s["model"]["repo"].endswith(target)]
        assert sorted(s["num_draft_tokens"] or 0 for s in group) == [0, 2, 4, 8]
    drafts = {s["draft_model"]["repo"] for s in specs if s["draft_model"]}
    assert drafts == {"mlx-community/Qwen3-0.6B-4bit"}


def test_models_are_pinned_to_commits():
    models = yaml.safe_load(DEFAULTS.read_text())["models"]
    for alias, model in models.items():
        assert re.fullmatch(r"[0-9a-f]{40}", model["revision"]), alias


@pytest.mark.parametrize("path", [EXP_A, EXP_B])
def test_every_config_is_accepted_by_bench(path):
    for spec in load_experiment(path, DEFAULTS):
        args = parse_args(spec_to_argv(spec))
        assert args.experiment_id == spec["experiment_id"]
        assert args.revision == spec["model"]["revision"]
        assert args.max_tokens == 256 and args.runs == 3 and args.temperature == 0.0
        assert args.enable_thinking is False
        if spec["draft_model"]:
            assert args.draft_revision == spec["draft_model"]["revision"]


def write(path, text):
    path.write_text(text)
    return path


@pytest.fixture
def defaults(tmp_path):
    return write(
        tmp_path / "defaults.yaml",
        "params: {runs: 3, max_tokens: 256}\n"
        "models: {m: {repo: org/m, revision: abc}, d: {repo: org/d}}\n",
    )


def test_overrides_and_skip_reason(tmp_path, defaults):
    exp = write(
        tmp_path / "e.yaml",
        "experiment_id: X\nparams: {runs: 2}\n"
        "configs:\n"
        "  - {config_id: c1, model: m, max_tokens: 64}\n"
        "  - {config_id: c2, model: m, skip_reason: RAM}\n",
    )
    c1, c2 = load_experiment(exp, defaults)
    assert c1["params"] == {"runs": 2, "max_tokens": 64}
    argv = spec_to_argv(c2)
    assert argv[-2:] == ["--skip-reason", "RAM"]
    assert parse_args(argv).skip_reason == "RAM"


@pytest.mark.parametrize(
    "configs,message",
    [
        ("[{config_id: c, model: nope}]", "registry"),
        ("[{config_id: c, model: m}, {config_id: c, model: m}]", "duplikat"),
        ("[{config_id: c, model: m, draft_model: d}]", "bersama"),
        ("[{config_id: c, model: m, max_token: 1}]", "tidak dikenal"),
        ("[{config_id: c, model: m, runs: true}]", "bertipe int"),
        ("[{config_id: c}]", "`model` wajib"),
    ],
)
def test_invalid_configs(tmp_path, defaults, configs, message):
    exp = write(tmp_path / "e.yaml", f"experiment_id: X\nconfigs: {configs}\n")
    with pytest.raises(ValueError, match=message):
        load_experiment(exp, defaults)


def test_dry_run_prints_bench_commands(capsys):
    assert main([str(EXP_B), "--defaults", str(DEFAULTS), "--dry-run", "--only",
                 "qwen3-4b-4bit-k4"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert "--num-draft-tokens 4" in lines[0]
    assert "--draft-model mlx-community/Qwen3-0.6B-4bit" in lines[0]
