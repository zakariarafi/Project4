"""CLI benchmark: satu konfigurasi model (target, opsional draft) × set prompt.

Contoh smoke run (satu prompt, satu run):

    sudo -v
    python -m src.bench \\
        --experiment-id smoke --config-id qwen3-0.6b-4bit \\
        --model mlx-community/Qwen3-0.6B-4bit \\
        --limit-prompts 1 --runs 1 --output data/raw/smoke.jsonl

Setiap run ditulis sebagai satu baris JSONL (lihat src/schemas.py). Run
`measured` yang sudah ada di file output dilewati, sehingga perintah yang
sama dapat dijalankan ulang untuk melanjutkan blok yang terhenti.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from importlib import metadata
from pathlib import Path

from src.power import PowerMonitor, WindowPower, energy_metrics
from src.schemas import (
    MIN_POWER_COVERAGE,
    SCHEMA_VERSION,
    WARMUP_RUN,
    record_key,
    validate_record,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m src.bench",
        description="Ukur throughput, memori puncak, dan J/token satu konfigurasi MLX.",
    )
    p.add_argument("--experiment-id", required=True, help="mis. A-size-precision")
    p.add_argument("--config-id", required=True, help="mis. qwen3-0.6b-4bit")
    p.add_argument("--model", required=True, help="ID model eksplisit (Hugging Face/MLX)")
    p.add_argument("--draft-model", help="ID draft model untuk speculative decoding")
    p.add_argument("--num-draft-tokens", type=int, help="k: token draft per langkah")
    p.add_argument("--revision", help="commit Hugging Face model target (pin)")
    p.add_argument("--draft-revision", help="commit Hugging Face draft model (pin)")
    p.add_argument("--prompts", type=Path, default=Path("prompts/gsm8k_10.jsonl"))
    p.add_argument("--limit-prompts", type=int, help="pakai N prompt pertama saja (smoke)")
    p.add_argument("--runs", type=int, default=3, help="pengulangan terukur per prompt")
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--enable-thinking", action="store_true",
        help="aktifkan mode thinking Qwen3 (default: non-thinking)",
    )
    p.add_argument("--warmup-tokens", type=int, default=32)
    p.add_argument("--output", type=Path, default=Path("data/raw/results.jsonl"))
    p.add_argument("--manifest-dir", type=Path, default=Path("data/manifests"))
    p.add_argument("--power-interval-ms", type=int, default=100)
    p.add_argument("--idle-seconds", type=float, default=20.0, help="idle awal blok")
    p.add_argument(
        "--reidle-every", type=int, default=10,
        help="ukur ulang idle setiap N run terukur (0 = hanya di awal)",
    )
    p.add_argument("--reidle-seconds", type=float, default=10.0)
    p.add_argument(
        "--no-power", action="store_true",
        help="tanpa powermetrics (uji pipeline saja; run berstatus incomplete)",
    )
    p.add_argument(
        "--skip-reason",
        help="jangan jalankan; tulis satu record skipped_resource_limit dengan alasan ini",
    )
    p.add_argument(
        "--allow-duplicates", action="store_true",
        help="jalankan ulang run yang sudah measured di file output",
    )
    args = p.parse_args(argv)

    if (args.draft_model is None) != (args.num_draft_tokens is None):
        p.error("--draft-model dan --num-draft-tokens harus dipakai bersama")
    if args.draft_revision and not args.draft_model:
        p.error("--draft-revision hanya berlaku dengan --draft-model")
    if args.num_draft_tokens is not None and args.num_draft_tokens <= 0:
        p.error("--num-draft-tokens harus > 0")
    if args.runs <= 0 or args.max_tokens <= 0:
        p.error("--runs dan --max-tokens harus > 0")
    return args


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_prompts(path: Path, limit: int | None = None) -> list[dict]:
    prompts = []
    seen = set()
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item.get("id"), str) or not isinstance(item.get("prompt"), str):
                raise ValueError(f"{path}:{lineno}: wajib punya `id` dan `prompt` string")
            if item["id"] in seen:
                raise ValueError(f"{path}:{lineno}: id duplikat {item['id']}")
            seen.add(item["id"])
            prompts.append(item)
    if not prompts:
        raise ValueError(f"{path}: tidak ada prompt")
    return prompts[:limit] if limit else prompts


def measured_keys(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    keys = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if record.get("status") == "measured":
                    keys.add(record_key(record))
    return keys


def plan_runs(args: argparse.Namespace, prompts: list[dict], done: set[tuple]) -> list[tuple]:
    """Urutan (run, prompt): pengulangan di luar agar drift tersebar ke semua prompt."""
    plan = []
    for run in range(args.runs):
        for prompt in prompts:
            key = (args.experiment_id, args.config_id, prompt["id"], run)
            if args.allow_duplicates or key not in done:
                plan.append((run, prompt))
    return plan


def base_record(args: argparse.Namespace, prompt_id: str, run: int, status: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": args.experiment_id,
        "config_id": args.config_id,
        "model": args.model,
        "draft_model": args.draft_model,
        "num_draft_tokens": args.num_draft_tokens,
        "prompt_id": prompt_id,
        "run": run,
        "status": status,
        "temperature": args.temperature,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "enable_thinking": args.enable_thinking,
        "generation_tokens": None,
        "generation_tps": None,
        "prompt_tokens": None,
        "prompt_tps": None,
        "peak_memory_gb": None,
        "duration_s": None,
        "idle_watts": None,
        "avg_watts": None,
        "joules_per_token": None,
        "energy_clipped": None,
        "power_interval_ms": None if args.no_power else args.power_interval_ms,
        "power_samples": None,
        "power_coverage": None,
        "draft_fraction": None,
        "output_sha256": None,
        "started_at": now_iso(),
        "finished_at": None,
        "error": None,
    }


def apply_power(
    record: dict, window: WindowPower | None, idle_watts: float | None
) -> None:
    """Isi field energi dan tentukan status akhir run yang berhasil generate."""
    if idle_watts is None:
        record["status"] = "incomplete"
        record["error"] = "pengukuran daya dinonaktifkan (--no-power)"
        return
    record["idle_watts"] = idle_watts
    if window is None:
        record["status"] = "incomplete"
        record["error"] = "tidak ada sampel daya pada jendela run"
        return
    record["avg_watts"] = window.avg_watts
    record["power_samples"] = window.samples
    record["power_coverage"] = window.coverage
    if window.coverage < MIN_POWER_COVERAGE:
        record["status"] = "incomplete"
        record["error"] = f"cakupan sampel daya {window.coverage:.2f} < {MIN_POWER_COVERAGE}"
        return
    jpt, clipped = energy_metrics(
        window.avg_watts, idle_watts, record["duration_s"], record["generation_tokens"]
    )
    record["joules_per_token"] = jpt
    record["energy_clipped"] = clipped
    record["status"] = "measured"


def append_record(path: Path, record: dict) -> None:
    errors = validate_record(record)
    if errors:
        raise ValueError(f"record tidak valid: {errors}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _command_output(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def write_manifest(args: argparse.Namespace, argv: list[str]) -> Path:
    """Metadata kondisi run (FR-13): mesin, OS, versi paket, dan command."""
    packages = {}
    for name in ("mlx", "mlx-lm", "mlx-metal", "transformers"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    memsize = _command_output(["sysctl", "-n", "hw.memsize"])
    manifest = {
        "created_at": now_iso(),
        "experiment_id": args.experiment_id,
        "config_id": args.config_id,
        "argv": argv,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "chip": _command_output(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "memory_gb": int(memsize) / 1024**3 if memsize and memsize.isdigit() else None,
        "macos": _command_output(["sw_vers", "-productVersion"]),
        "packages": packages,
        "git_revision": _command_output(["git", "rev-parse", "HEAD"]),
        "model_revision": args.revision,
        "draft_revision": args.draft_revision,
        "power_interval_ms": None if args.no_power else args.power_interval_ms,
    }
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = args.manifest_dir / f"{args.experiment_id}_{args.config_id}_{stamp}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_prompt_tokens(tokenizer, prompt: str, enable_thinking: bool) -> list[int]:
    messages = [{"role": "user", "content": prompt}]
    return tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, enable_thinking=enable_thinking
    )


def _reset_peak_memory(mx) -> None:
    reset = getattr(mx, "reset_peak_memory", None) or getattr(mx.metal, "reset_peak_memory")
    reset()


def generate_once(model, tokenizer, prompt_tokens, args, draft_model, max_tokens) -> dict:
    """Satu generasi; kembalikan metrik dan batas waktu monotonic run."""
    import mlx.core as mx
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.random.seed(args.seed)
    _reset_peak_memory(mx)
    kwargs = {"max_tokens": max_tokens, "sampler": make_sampler(temp=args.temperature)}
    if draft_model is not None:
        kwargs["draft_model"] = draft_model
        kwargs["num_draft_tokens"] = args.num_draft_tokens

    pieces = []
    drafted = 0
    last = None
    # duration_s = jendela end-to-end panggilan generate, termasuk prefill.
    t0 = time.monotonic()
    for response in stream_generate(model, tokenizer, prompt_tokens, **kwargs):
        pieces.append(response.text)
        drafted += bool(getattr(response, "from_draft", False))
        last = response
    t1 = time.monotonic()
    if last is None or last.generation_tokens <= 0:
        raise RuntimeError("tidak ada token yang dihasilkan")

    draft_fraction = None
    if draft_model is not None and hasattr(last, "from_draft"):
        draft_fraction = drafted / last.generation_tokens
    return {
        "t0": t0,
        "t1": t1,
        "generation_tokens": last.generation_tokens,
        "generation_tps": float(last.generation_tps),
        "prompt_tokens": last.prompt_tokens,
        "prompt_tps": float(last.prompt_tps),
        "peak_memory_gb": float(last.peak_memory),
        "duration_s": t1 - t0,
        "draft_fraction": draft_fraction,
        "output_sha256": hashlib.sha256("".join(pieces).encode("utf-8")).hexdigest(),
    }


def run_block(args: argparse.Namespace, prompts: list[dict], plan: list[tuple]) -> int:
    from mlx_lm import load

    monitor = None if args.no_power else PowerMonitor(args.power_interval_ms)
    failures = 0
    try:
        idle_watts = None
        if monitor:
            monitor.start()
            print(f"mengukur idle {args.idle_seconds:.0f} s ...", flush=True)
            idle_watts = monitor.measure_idle(args.idle_seconds)
            print(f"idle = {idle_watts:.2f} W", flush=True)

        model, tokenizer = load(args.model, revision=args.revision)
        draft_model = None
        if args.draft_model:
            draft_model, draft_tokenizer = load(args.draft_model, revision=args.draft_revision)
            # Sama seperti CLI mlx_lm.generate: draft wajib berbagi vocab target.
            if draft_tokenizer.vocab_size != tokenizer.vocab_size:
                raise ValueError("tokenizer draft model tidak cocok dengan model target")

        # Warm-up: dicatat terpisah (status warmup) dan tidak dianalisis (FR-03).
        warm = base_record(args, prompts[0]["id"], WARMUP_RUN, "warmup")
        tokens = build_prompt_tokens(tokenizer, prompts[0]["prompt"], args.enable_thinking)
        metrics = generate_once(model, tokenizer, tokens, args, draft_model, args.warmup_tokens)
        warm.update({k: v for k, v in metrics.items() if k in warm})
        warm["finished_at"] = now_iso()
        append_record(args.output, warm)

        for index, (run, prompt) in enumerate(plan):
            if monitor and args.reidle_every and index and index % args.reidle_every == 0:
                idle_watts = monitor.measure_idle(args.reidle_seconds)
                print(f"idle ulang = {idle_watts:.2f} W", flush=True)
            record = base_record(args, prompt["id"], run, "failed")
            try:
                tokens = build_prompt_tokens(tokenizer, prompt["prompt"], args.enable_thinking)
                metrics = generate_once(
                    model, tokenizer, tokens, args, draft_model, args.max_tokens
                )
                record.update({k: v for k, v in metrics.items() if k in record})
                window = monitor.window(metrics["t0"], metrics["t1"]) if monitor else None
                apply_power(record, window, idle_watts)
            except Exception as exc:  # run gagal tetap dicatat, bukan dihapus
                record["status"] = "failed"
                record["error"] = f"{type(exc).__name__}: {exc}"[:500]
            record["finished_at"] = now_iso()
            append_record(args.output, record)
            failures += record["status"] != "measured"
            print(
                f"[{index + 1}/{len(plan)}] {prompt['id']} run={run} "
                f"status={record['status']} tps={record['generation_tps']} "
                f"J/tok={record['joules_per_token']}",
                flush=True,
            )
    finally:
        if monitor:
            monitor.stop()
    return failures


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)

    if args.skip_reason:
        record = base_record(args, "*", WARMUP_RUN, "skipped_resource_limit")
        record["error"] = args.skip_reason
        record["finished_at"] = record["started_at"]
        append_record(args.output, record)
        print(f"{args.config_id} dicatat sebagai skipped_resource_limit")
        return 0

    prompts = load_prompts(args.prompts, args.limit_prompts)
    plan = plan_runs(args, prompts, measured_keys(args.output))
    if not plan:
        print("semua run measured sudah ada; tidak ada yang dijalankan")
        return 0
    manifest = write_manifest(args, argv)
    print(f"manifest: {manifest}; {len(plan)} run direncanakan", flush=True)
    failures = run_block(args, prompts, plan)
    print(f"selesai: {len(plan) - failures} measured, {failures} tidak measured")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
