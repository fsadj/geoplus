#!/usr/bin/env python3
"""Generate charts for the test report from dynamic experiment data."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geoplus.analysis.experiment_stats import summarize_before_after
from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()
summary = summarize_before_after(compare_variant="after_nozws")
dataset_labels = summary["labels"]
datasets = summary["dataset_ids"]
before_ref_pct = summary["before_ref_pct"]
after_ref_pct = summary["compare_ref_pct"]
before_word_pct = summary["before_word_pct"]
after_word_pct = summary["compare_word_pct"]
ref_improve = summary["ref_improve"]
word_improve = summary["word_improve"]

C_BEFORE = "#94a3b8"
C_AFTER = "#3b82f6"
C_REF = "#2563eb"
C_WORD = "#7c3aed"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.dpi": 200,
})

import warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*Glyph.*missing.*")

x = np.arange(len(datasets))

fig, ax = plt.subplots(figsize=(7.5, 3.5))
w = 0.35
bars1 = ax.bar(x - w / 2, before_ref_pct, w, color=C_BEFORE, edgecolor="white", linewidth=0.5, label="Before (before.md)")
bars2 = ax.bar(x + w / 2, after_ref_pct, w, color=C_AFTER, edgecolor="white", linewidth=0.5, label="Baseline (after_nozws.md)")
for bar, val in zip(bars1, before_ref_pct):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color="#64748b")
for bar, val in zip(bars2, after_ref_pct):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color=C_AFTER, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=6)
ax.set_ylabel("Citation Count Ratio (%)", fontsize=9)
ax.set_title("Citation Count Ratio: Before vs Default No-ZWS Baseline", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 90)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart1_citation_ratio_comparison.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 3.5))
bars1 = ax.bar(x - w / 2, before_word_pct, w, color=C_BEFORE, edgecolor="white", linewidth=0.5, label="Before (before.md)")
bars2 = ax.bar(x + w / 2, after_word_pct, w, color=C_WORD, edgecolor="white", linewidth=0.5, label="Baseline (after_nozws.md)")
for bar, val in zip(bars1, before_word_pct):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color="#64748b")
for bar, val in zip(bars2, after_word_pct):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color=C_WORD, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=6)
ax.set_ylabel("Word Content Ratio (%)", fontsize=9)
ax.set_title("Word Content Ratio: Before vs Default No-ZWS Baseline", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 110)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart2_word_ratio_comparison.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 3.2))
ax.plot(x, ref_improve, "o-", color=C_REF, linewidth=2, markersize=6, label="Citation Ratio Improvement (pp)")
ax.plot(x, word_improve, "s--", color=C_WORD, linewidth=2, markersize=6, label="Word Ratio Improvement (pp)")
for index in range(len(datasets)):
    ax.annotate(f"{ref_improve[index]:.1f}", (x[index], ref_improve[index]), textcoords="offset points", xytext=(0, 8), fontsize=5.5, ha="center", color=C_REF)
    ax.annotate(f"{word_improve[index]:.1f}", (x[index], word_improve[index]), textcoords="offset points", xytext=(0, -12), fontsize=5.5, ha="center", color=C_WORD)
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=6)
ax.set_ylabel("Improvement (pp)", fontsize=9)
ax.set_title("Optimization Effect: Improvement per Dataset", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart3_improvement_per_dataset.png")
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.2))
avg_before_ref = summary["avg_before_ref"]
avg_after_ref = summary["avg_compare_ref"]
axes[0].bar(["Before"], [avg_before_ref], color=C_BEFORE, width=0.4)
axes[0].bar(["Baseline"], [avg_after_ref], color=C_AFTER, width=0.4)
axes[0].text(0, avg_before_ref + 1.5, f"{avg_before_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color="#475569")
axes[0].text(1, avg_after_ref + 1.5, f"{avg_after_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_AFTER)
axes[0].set_ylabel("%", fontsize=9)
axes[0].set_title("Avg Citation Ratio", fontsize=10, fontweight="bold")
axes[0].set_ylim(0, 75)
axes[0].grid(axis="y", alpha=0.3)

avg_before_word = summary["avg_before_word"]
avg_after_word = summary["avg_compare_word"]
axes[1].bar(["Before"], [avg_before_word], color=C_BEFORE, width=0.4)
axes[1].bar(["Baseline"], [avg_after_word], color=C_WORD, width=0.4)
axes[1].text(0, avg_before_word + 1.5, f"{avg_before_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color="#475569")
axes[1].text(1, avg_after_word + 1.5, f"{avg_after_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_WORD)
axes[1].set_ylabel("%", fontsize=9)
axes[1].set_title("Avg Word Ratio", fontsize=10, fontweight="bold")
axes[1].set_ylim(0, 85)
axes[1].grid(axis="y", alpha=0.3)

fig.suptitle(f"Overall Baseline Performance ({len(datasets)} Datasets)", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart4_avg_summary.png")
plt.close(fig)

total_improve = [ref + word for ref, word in zip(ref_improve, word_improve)]
sorted_idx = np.argsort(total_improve)[::-1]
top_count = min(5, len(sorted_idx))
top_idx = sorted_idx[:top_count]

fig, ax = plt.subplots(figsize=(7, 3.2))
x_top = np.arange(top_count)
top_ref = [ref_improve[index] for index in top_idx]
top_word = [word_improve[index] for index in top_idx]
top_labels = [dataset_labels[index] for index in top_idx]
ax.bar(x_top - 0.15, top_ref, 0.3, color=C_REF, edgecolor="white", label="Citation Ratio Improvement (pp)")
ax.bar(x_top + 0.15, top_word, 0.3, color=C_WORD, edgecolor="white", label="Word Ratio Improvement (pp)")
for index in range(top_count):
    ax.text(index - 0.15, top_ref[index] + 1, f"{top_ref[index]:.1f}", ha="center", fontsize=8, fontweight="bold", color=C_REF)
    ax.text(index + 0.15, top_word[index] + 1, f"{top_word[index]:.1f}", ha="center", fontsize=8, fontweight="bold", color=C_WORD)
ax.set_xticks(x_top)
ax.set_xticklabels(top_labels, fontsize=8)
ax.set_ylabel("Improvement (pp)", fontsize=9)
ax.set_title("Top Combined Improvement Datasets", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart5_top5_improvement.png")
plt.close(fig)

print("5 charts saved to outputs/charts/")
print("  chart1_citation_ratio_comparison.png")
print("  chart2_word_ratio_comparison.png")
print("  chart3_improvement_per_dataset.png")
print("  chart4_avg_summary.png")
print("  chart5_top5_improvement.png")
