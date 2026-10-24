"""Pembuat record hasil yang valid untuk test."""

from src.schemas import FIELDS, SCHEMA_VERSION


def measured_record(**overrides) -> dict:
    record = {name: None for name in FIELDS}
    record.update(
        schema_version=SCHEMA_VERSION,
        experiment_id="A-size-precision",
        config_id="qwen3-0.6b-4bit",
        model="mlx-community/Qwen3-0.6B-4bit",
        prompt_id="gsm8k-001",
        run=0,
        status="measured",
        temperature=0.0,
        seed=0,
        max_tokens=256,
        enable_thinking=False,
        generation_tokens=256,
        generation_tps=180.5,
        prompt_tokens=80,
        prompt_tps=900.0,
        peak_memory_gb=0.6,
        duration_s=1.5,
        idle_watts=2.0,
        avg_watts=12.0,
        joules_per_token=0.06,
        energy_clipped=False,
        power_interval_ms=100,
        power_samples=15,
        power_coverage=0.98,
        output_sha256="ab" * 32,
        started_at="2026-10-21T10:00:00+07:00",
        finished_at="2026-10-21T10:00:02+07:00",
    )
    record.update(overrides)
    return record
