"""Grafik final dari data/processed/summary.csv.

    python -m src.plot

Semua grafik memakai nilai agregat (rata-rata ± simpangan baku run measured),
bukan run terbaik:
- plots/throughput_by_model_size.png  Eksperimen A, token/s (wajib, PRD §10)
- plots/energy_per_token.png          Eksperimen A, J/token (wajib, PRD §10)
- plots/speculative_by_k.png          Eksperimen B, bila datanya ada

Warna mengikuti presisi model di semua grafik (bf16, 8-bit, 4-bit), sehingga
target bf16/4-bit di Eksperimen B memakai warna yang sama dengan Eksperimen A.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Palet referensi (divalidasi: 3 slot pertama lolos CVD all-pairs pada latar
# terang). Aqua < 3:1 terhadap latar, jadi setiap nilai diberi label langsung.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
PRECISIONS = {
    "bf16": ("bf16", "#2a78d6"),
    "8bit": ("8-bit", "#eb6834"),
    "4bit": ("4-bit", "#1baf7a"),
}
SIZES = (0.6, 1.7, 4.0)
TEXT_COLUMNS = {
    "experiment_id", "config_id", "model", "precision", "draft_model", "mode",
    "complete", "notes",
}


def read_summary(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {}
            for key, value in raw.items():
                if value == "":
                    row[key] = None
                elif key in TEXT_COLUMNS:
                    row[key] = value
                else:
                    row[key] = float(value)
            rows.append(row)
    return rows


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.grid(axis="y", color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelcolor=INK_SECONDARY, length=0, labelsize=8)
    ax.yaxis.label.set_color(INK_SECONDARY)


def _value_label(ax, x: float, top: float, value: float) -> None:
    ax.annotate(
        f"{value:.3g}", (x, top), xytext=(0, 3), textcoords="offset points",
        ha="center", va="bottom", fontsize=7, color=INK_SECONDARY,
    )


def plot_size_precision(
    rows: list[dict], metric: str, ylabel: str, title: str, path: Path,
    experiment_id: str = "A-size-precision",
) -> None:
    """Kolom berkelompok: ukuran model di sumbu x, satu kolom per presisi."""
    data = {
        (r["model_size_b"], r["precision"]): r
        for r in rows
        if r["experiment_id"] == experiment_id and r["mode"] == "baseline"
    }
    if not data:
        raise ValueError(f"tidak ada baris {experiment_id} di summary")

    fig, ax = plt.subplots(figsize=(7.5, 4.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)

    width = 0.2
    gap = 0.02
    tops = []
    for i, (precision, (_, color)) in enumerate(PRECISIONS.items()):
        offset = (i - 1) * (width + gap)
        for j, size in enumerate(SIZES):
            x = j + offset
            row = data.get((size, precision))
            mean = row.get(f"{metric}_mean") if row else None
            if mean is None:
                reason = "dilewati" if row and row.get("n_skipped") else "belum ada data"
                ax.annotate(
                    reason, (x, 0), xytext=(0, 4), textcoords="offset points",
                    rotation=90, ha="center", va="bottom", fontsize=7, color=MUTED,
                )
                continue
            std = row.get(f"{metric}_std") or 0.0
            ax.bar(x, mean, width=width, color=color, zorder=2)
            if std:
                ax.errorbar(
                    x, mean, yerr=std, fmt="none", ecolor=INK_SECONDARY,
                    elinewidth=1, capsize=0, zorder=3,
                )
            _value_label(ax, x, mean + std, mean)
            tops.append(mean + std)

    ax.set_xticks(range(len(SIZES)), [f"Qwen3-{s:g}B" for s in SIZES])
    ax.set_ylabel(ylabel, fontsize=9)
    if tops:
        ax.set_ylim(0, max(tops) * 1.15)
    ax.set_title(title, loc="left", color=INK, fontsize=11, pad=12)
    handles = [Patch(color=color, label=label) for label, color in PRECISIONS.values()]
    ax.legend(
        handles=handles, loc="lower right", bbox_to_anchor=(1, 1.0), ncol=3,
        frameon=False, fontsize=8, labelcolor=INK_SECONDARY, handlelength=1, handleheight=1,
    )
    fig.text(
        0.01, 0.01, "Batang: rata-rata run measured. Garis: ±1 simpangan baku. Batch size 1.",
        fontsize=7, color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def plot_speculative(rows: list[dict], path: Path, experiment_id: str = "B-speculative") -> bool:
    """Throughput dan J/token terhadap k, satu garis per presisi target."""
    data = [r for r in rows if r["experiment_id"] == experiment_id]
    if not data:
        return False
    k_values = sorted({int(r["num_draft_tokens"]) for r in data if r["num_draft_tokens"]})
    positions = {0: 0, **{k: i + 1 for i, k in enumerate(k_values)}}
    labels = ["tanpa draft"] + [f"k={k}" for k in k_values]
    drafts = sorted({r["draft_model"] for r in data if r["draft_model"]})

    fig, axes = plt.subplots(1, 2, figsize=(9, 4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    panels = (
        ("generation_tps", "Throughput generasi (token/s)"),
        ("joules_per_token", "Energi per token keluaran (J/token)"),
    )
    for ax, (metric, ylabel) in zip(axes, panels):
        _style(ax)
        tops = []
        for precision, (label, color) in PRECISIONS.items():
            points = sorted(
                (positions[int(r["num_draft_tokens"] or 0)], r[f"{metric}_mean"],
                 r[f"{metric}_std"] or 0.0)
                for r in data
                if r["precision"] == precision and r[f"{metric}_mean"] is not None
            )
            if not points:
                continue
            xs, ys, errs = zip(*points)
            ax.errorbar(
                xs, ys, yerr=errs, color=color, ecolor=color, elinewidth=1, linewidth=2,
                marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5,
                solid_capstyle="round", solid_joinstyle="round", label=label, zorder=3,
            )
            ax.annotate(
                f"{label} {ys[-1]:.3g}", (xs[-1], ys[-1]), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=7, color=INK_SECONDARY,
            )
            tops.extend(y + e for y, e in zip(ys, errs))
        ax.set_xticks(range(len(labels)), labels)
        ax.set_xlim(-0.3, len(labels) - 0.4)
        if tops:
            ax.set_ylim(0, max(tops) * 1.15)
        ax.set_title(ylabel, loc="left", color=INK, fontsize=9)

    handles = [
        Patch(color=color, label=f"Qwen3-4B {label}")
        for precision, (label, color) in PRECISIONS.items()
        if any(r["precision"] == precision for r in data)
    ]
    fig.legend(
        handles=handles, loc="upper right", ncol=len(handles), frameon=False,
        fontsize=8, labelcolor=INK_SECONDARY, handlelength=1, handleheight=1,
    )
    draft_text = drafts[0].split("/")[-1] if len(drafts) == 1 else ", ".join(drafts)
    fig.suptitle(
        f"Speculative decoding, draft {draft_text}", x=0.01, ha="left",
        color=INK, fontsize=11,
    )
    fig.text(
        0.01, 0.01, "Titik: rata-rata run measured. Garis vertikal: ±1 simpangan baku.",
        fontsize=7, color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.plot", description="Buat grafik final dari summary.csv.",
    )
    p.add_argument("--summary", type=Path, default=Path("data/processed/summary.csv"))
    p.add_argument("--out-dir", type=Path, default=Path("plots"))
    p.add_argument("--experiment-a", default="A-size-precision")
    p.add_argument("--experiment-b", default="B-speculative")
    args = p.parse_args(argv)

    rows = read_summary(args.summary)
    try:
        plot_size_precision(
            rows, "generation_tps", "Throughput generasi (token/s)",
            "Throughput menurut ukuran dan presisi model",
            args.out_dir / "throughput_by_model_size.png", args.experiment_a,
        )
        plot_size_precision(
            rows, "joules_per_token", "Energi per token keluaran (J/token)",
            "Energi per token menurut ukuran dan presisi model",
            args.out_dir / "energy_per_token.png", args.experiment_a,
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"ditulis: {args.out_dir}/throughput_by_model_size.png, energy_per_token.png")
    if plot_speculative(rows, args.out_dir / "speculative_by_k.png", args.experiment_b):
        print(f"ditulis: {args.out_dir}/speculative_by_k.png")
    else:
        print(f"tidak ada data {args.experiment_b}; grafik speculative dilewati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
