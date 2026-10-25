from src.aggregate import summarize, write_summary
from src.plot import main, read_summary
from tests.factories import measured_record

PNG = b"\x89PNG\r\n\x1a\n"
SIZES = {"0.6": 200.0, "1.7": 90.0, "4": 40.0}
SCALE = {"bf16": 1.0, "8bit": 1.6, "4bit": 2.4}


def synthetic_records():
    records = []
    for size, tps in SIZES.items():
        for precision, scale in SCALE.items():
            config_id = f"qwen3-{size}b-{precision}"
            model = f"mlx-community/Qwen3-{size}B-{precision}"
            if size == "4" and precision == "bf16":
                records.append(measured_record(
                    config_id=config_id, model=model, status="skipped_resource_limit",
                    prompt_id="*", run=-1, error="RAM tidak cukup",
                ))
                continue
            for run in range(3):
                records.append(measured_record(
                    config_id=config_id, model=model, run=run,
                    generation_tps=tps * scale * (1 + 0.02 * run),
                    joules_per_token=0.5 / (tps * scale) * 40 * (1 + 0.03 * run),
                ))
    for precision in ("bf16", "4bit"):
        model = f"mlx-community/Qwen3-4B-{precision}"
        for k, speed in ((None, 1.0), (2, 1.3), (4, 1.5), (8, 1.35)):
            for run in range(3):
                records.append(measured_record(
                    experiment_id="B-speculative",
                    config_id=f"qwen3-4b-{precision}-{'k%d' % k if k else 'baseline'}",
                    model=model, draft_model="mlx-community/Qwen3-0.6B-4bit" if k else None,
                    num_draft_tokens=k, draft_fraction=0.6 if k else None, run=run,
                    generation_tps=40 * SCALE[precision] * speed * (1 + 0.02 * run),
                    joules_per_token=0.5 / (SCALE[precision] * speed),
                ))
    return records


def test_plots_are_written(tmp_path):
    summary = tmp_path / "summary.csv"
    write_summary(summarize(synthetic_records()), summary)
    rows = read_summary(summary)
    assert rows[0]["model_size_b"] == 0.6 and rows[0]["config_id"] == "qwen3-0.6b-bf16"

    out = tmp_path / "plots"
    assert main(["--summary", str(summary), "--out-dir", str(out)]) == 0
    for name in ("throughput_by_model_size.png", "energy_per_token.png", "speculative_by_k.png"):
        assert (out / name).read_bytes().startswith(PNG), name


def test_missing_experiment_a_fails(tmp_path, capsys):
    summary = tmp_path / "summary.csv"
    write_summary(summarize([measured_record(experiment_id="smoke")]), summary)
    assert main(["--summary", str(summary), "--out-dir", str(tmp_path)]) == 1
    assert "A-size-precision" in capsys.readouterr().err
