#!/usr/bin/env python3
"""Generate evidence charts for report2 about official scoring ambiguities."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from simulator.data import load_json_item
from simulator.objective import CONTEST_CALIBRATED_V1_PROFILE, LEGACY_OBJECTIVE_PROFILE, score_objective

IMAGE_DIR = REPO_ROOT / "outputs" / "charts"
OUTPUT_SUMMARY = REPO_ROOT / "outputs" / "report2_evidence_summary.json"
TUNING_PATH = REPO_ROOT / "outputs" / "objective_tuning" / "tune_objective_20260513_161510.json"
ITEM_GLOB = REPO_ROOT / "outputs" / "datasets"

warnings.filterwarnings("ignore", category=UserWarning)
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "figure.dpi": 200,
    }
)

COLOR_OFFICIAL = "#0f172a"
COLOR_CALIBRATED = "#2563eb"
COLOR_LEGACY = "#f97316"
COLOR_WORD_VOLU = "#2563eb"
COLOR_POSI_PROM = "#10b981"
COLOR_WORD_POSI = "#ef4444"
TEXT = "#0f172a"


def dataset_label_from_path(path: Path) -> str:
    dataset_id = path.stem.removeprefix("simulator_item_ds")
    return f"DS{dataset_id}"


def load_proxy_samples() -> list[dict]:
    sample_paths = sorted(ITEM_GLOB.glob("*/simulator_item_ds*.json"), key=lambda path: int(path.parent.name))
    rows = []
    for path in sample_paths:
        item = load_json_item(path)
        if item.generated_original_answer is None or item.visibility_before is None:
            continue
        legacy = score_objective(
            item.generated_original_answer,
            target_source_id=item.target.source_id,
            profile=LEGACY_OBJECTIVE_PROFILE,
        )
        calibrated = score_objective(
            item.generated_original_answer,
            target_source_id=item.target.source_id,
            profile=CONTEST_CALIBRATED_V1_PROFILE,
        )
        rows.append(
            {
                "label": dataset_label_from_path(path),
                "legacy_word_volu": legacy.word_volu,
                "legacy_posi_prom": legacy.posi_prom,
                "legacy_word_posi": legacy.word_posi,
                "calibrated_word_volu": calibrated.word_volu,
                "calibrated_posi_prom": calibrated.posi_prom,
                "calibrated_word_posi": calibrated.word_posi,
                "delta_word_volu": calibrated.word_volu - legacy.word_volu,
                "delta_posi_prom": calibrated.posi_prom - legacy.posi_prom,
                "delta_word_posi": calibrated.word_posi - legacy.word_posi,
            }
        )
    return rows


def load_tuning() -> dict:
    return json.loads(TUNING_PATH.read_text(encoding="utf-8"))


def load_reference_sample(tuning: dict) -> dict:
    sample = next(item for item in tuning["samples"] if item["label"] == "social_phobia_reference")
    legacy = score_objective(
        sample["answer_text"],
        target_source_id=sample["target_source_id"],
        profile=LEGACY_OBJECTIVE_PROFILE,
    )
    calibrated = score_objective(
        sample["answer_text"],
        target_source_id=sample["target_source_id"],
        profile=CONTEST_CALIBRATED_V1_PROFILE,
    )
    return {
        "label": sample["label"],
        "official_word_volu": sample["official_word_volu"],
        "official_posi_prom": sample["official_posi_prom"],
        "official_word_posi": sample["official_word_posi"],
        "legacy_word_volu": legacy.word_volu,
        "legacy_posi_prom": legacy.posi_prom,
        "legacy_word_posi": legacy.word_posi,
        "calibrated_word_volu": calibrated.word_volu,
        "calibrated_posi_prom": calibrated.posi_prom,
        "calibrated_word_posi": calibrated.word_posi,
        "legacy_word_volu_gap": legacy.word_volu - sample["official_word_volu"],
        "legacy_posi_prom_gap": legacy.posi_prom - sample["official_posi_prom"],
        "legacy_word_posi_gap": legacy.word_posi - sample["official_word_posi"],
        "calibrated_word_volu_gap": calibrated.word_volu - sample["official_word_volu"],
        "calibrated_posi_prom_gap": calibrated.posi_prom - sample["official_posi_prom"],
        "calibrated_word_posi_gap": calibrated.word_posi - sample["official_word_posi"],
    }


def mean_abs(values: list[float]) -> float:
    return sum(abs(value) for value in values) / len(values) if values else 0.0


def build_summary(proxy_samples: list[dict], reference_sample: dict, tuning: dict) -> dict:
    top_profiles = tuning["results"][:5]
    return {
        "proxy_sample_count": len(proxy_samples),
        "reference_sample": reference_sample,
        "proxy_mean_abs_delta_word_volu": mean_abs([row["delta_word_volu"] for row in proxy_samples]),
        "proxy_mean_abs_delta_posi_prom": mean_abs([row["delta_posi_prom"] for row in proxy_samples]),
        "proxy_mean_abs_delta_word_posi": mean_abs([row["delta_word_posi"] for row in proxy_samples]),
        "largest_proxy_word_posi_shift": max(proxy_samples, key=lambda row: abs(row["delta_word_posi"])),
        "top_profiles": [
            {
                "profile_name": item["profile_name"],
                "word_volu_mae": item["word_volu_mae"],
                "posi_prom_mae": item["posi_prom_mae"],
                "word_posi_mae": item["word_posi_mae"],
                "mean_abs_error": item["mean_abs_error"],
            }
            for item in top_profiles
        ],
    }


def plot_reference_alignment(reference_sample: dict) -> None:
    metrics = ["word_volu", "posi_prom", "word_posi"]
    labels = ["word_volu", "posi_prom", "word_posi"]
    x = np.arange(len(metrics))
    width = 0.24
    official = [reference_sample[f"official_{metric}"] for metric in metrics]
    legacy = [reference_sample[f"legacy_{metric}"] for metric in metrics]
    calibrated = [reference_sample[f"calibrated_{metric}"] for metric in metrics]

    fig, ax = plt.subplots(figsize=(7.8, 4.0))
    ax.bar(x - width, official, width, color=COLOR_OFFICIAL, edgecolor="white", linewidth=0.5, label="Official Reference")
    ax.bar(x, legacy, width, color=COLOR_LEGACY, edgecolor="white", linewidth=0.5, label="Public-Formula Replay")
    ax.bar(x + width, calibrated, width, color=COLOR_CALIBRATED, edgecolor="white", linewidth=0.5, label="Calibrated Replay")
    for idx, metric in enumerate(metrics):
        gap = reference_sample[f"calibrated_{metric}_gap"]
        ax.text(x[idx] + width, max(official[idx], calibrated[idx], legacy[idx]) + 0.8, f"{gap:+.2f}", ha="center", va="bottom", fontsize=7, fontweight="bold", color=COLOR_CALIBRATED)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Score")
    ax.set_title("Official Reference Sample: Gaps Concentrate On word_posi", fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGE_DIR / "report2_smoke_alignment.png")
    plt.close(fig)


def plot_proxy_metric_shift(proxy_samples: list[dict]) -> None:
    labels = [row["label"] for row in proxy_samples]
    x = np.arange(len(labels))
    width = 0.22
    word_volu = [row["delta_word_volu"] for row in proxy_samples]
    posi_prom = [row["delta_posi_prom"] for row in proxy_samples]
    word_posi = [row["delta_word_posi"] for row in proxy_samples]

    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    ax.bar(x - width, word_volu, width, color=COLOR_WORD_VOLU, edgecolor="white", linewidth=0.5, label="Δ word_volu")
    ax.bar(x, posi_prom, width, color=COLOR_POSI_PROM, edgecolor="white", linewidth=0.5, label="Δ posi_prom")
    ax.bar(x + width, word_posi, width, color=COLOR_WORD_POSI, edgecolor="white", linewidth=0.5, label="Δ word_posi")
    for idx, value in enumerate(word_posi):
        ax.text(x[idx] + width, value + 0.15, f"{value:+.2f}", ha="center", va="bottom", fontsize=6, fontweight="bold", color=COLOR_WORD_POSI)
    ax.axhline(y=0, color="#475569", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Calibrated - Public-Formula Replay")
    ax.set_title("Proxy Corpus: Denominator Change Mainly Moves word_posi", fontweight="bold")
    ax.legend(fontsize=8, ncol=3)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGE_DIR / "report2_word_posi_gap.png")
    plt.close(fig)


def plot_profile_fit(tuning: dict) -> None:
    top = tuning["results"][:5]
    labels = [
        item["profile_name"]
        .replace("split=punct_or_newline|dedup=unique|credit=unique_refs|pos=share|", "")
        .replace("denom=total_weighted_chars|", "weighted/")
        for item in top
    ]
    x = np.arange(len(labels))
    width = 0.22
    word_volu = [item["word_volu_mae"] for item in top]
    posi_prom = [item["posi_prom_mae"] for item in top]
    word_posi = [item["word_posi_mae"] for item in top]

    fig, ax = plt.subplots(figsize=(9.2, 4.1))
    ax.bar(x - width, word_volu, width, color=COLOR_WORD_VOLU, edgecolor="white", linewidth=0.5, label="word_volu MAE")
    ax.bar(x, posi_prom, width, color=COLOR_POSI_PROM, edgecolor="white", linewidth=0.5, label="posi_prom MAE")
    ax.bar(x + width, word_posi, width, color=COLOR_WORD_POSI, edgecolor="white", linewidth=0.5, label="word_posi MAE")
    for idx, value in enumerate(word_posi):
        ax.text(x[idx] + width, value + 0.05, f"{value:.2f}", ha="center", va="bottom", fontsize=6, fontweight="bold", color=COLOR_WORD_POSI)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Mean Absolute Error")
    ax.set_title("Mixed Evidence Search: The Remaining Error Still Concentrates On word_posi", fontweight="bold")
    ax.legend(fontsize=8, ncol=3)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGE_DIR / "report2_profile_fit.png")
    plt.close(fig)


def plot_denominator_effect(proxy_samples: list[dict], reference_sample: dict) -> None:
    labels = [row["label"] for row in proxy_samples] + ["Official Ref"]
    legacy = [row["legacy_word_posi"] for row in proxy_samples] + [reference_sample["legacy_word_posi"]]
    calibrated = [row["calibrated_word_posi"] for row in proxy_samples] + [reference_sample["calibrated_word_posi"]]
    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8.8, 4.0))
    ax.bar(x - width / 2, legacy, width, color=COLOR_LEGACY, edgecolor="white", linewidth=0.5, label="Public-Formula Replay")
    ax.bar(x + width / 2, calibrated, width, color=COLOR_CALIBRATED, edgecolor="white", linewidth=0.5, label="Calibrated Replay")
    for idx, value in enumerate(calibrated):
        delta = value - legacy[idx]
        ax.text(x[idx] + width / 2, max(value, legacy[idx]) + 0.25, f"{delta:+.2f}", ha="center", va="bottom", fontsize=6, fontweight="bold", color=COLOR_CALIBRATED)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("word_posi")
    ax.set_title("Changing The Denominator Reprices word_posi Across Proxy And Reference Samples", fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGE_DIR / "report2_denominator_effect.png")
    plt.close(fig)


def main() -> None:
    proxy_samples = load_proxy_samples()
    tuning = load_tuning()
    reference_sample = load_reference_sample(tuning)
    summary = build_summary(proxy_samples, reference_sample, tuning)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    plot_reference_alignment(reference_sample)
    plot_proxy_metric_shift(proxy_samples)
    plot_profile_fit(tuning)
    plot_denominator_effect(proxy_samples, reference_sample)

    print(f"saved {IMAGE_DIR / 'report2_smoke_alignment.png'}")
    print(f"saved {IMAGE_DIR / 'report2_word_posi_gap.png'}")
    print(f"saved {IMAGE_DIR / 'report2_profile_fit.png'}")
    print(f"saved {IMAGE_DIR / 'report2_denominator_effect.png'}")
    print(f"saved {OUTPUT_SUMMARY}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
