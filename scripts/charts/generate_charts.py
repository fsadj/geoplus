#!/usr/bin/env python3
"""Generate charts for the test report from count_references data."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()

# ── Data from count_references.py runs ──────────────────────────
datasets = list(range(1, 15))
topics = [
    "DS1\nCognition",
    "DS2\nHormones",
    "DS3\nLanguage",
    "DS4\nMemory",
    "DS5\nAI & Jobs",
    "DS6\nGene Edit",
    "DS7\nGMO Safety",
    "DS8\nNuclear",
    "DS9\nAnimal Test",
    "DS10\nSurveillance",
    "DS11\nVaccination",
    "DS12\n5G Radiation",
    "DS13\nCrypto",
    "DS14\nMetaverse",
]

before_ref_pct = [17.6, 14.8, 22.2, 17.4, 10.5, 15.0, 6.2, 9.1, 11.1, 15.4, 17.6, 10.0, 14.3, 8.3]
after_ref_pct  = [36.0, 63.6, 53.6, 57.9, 55.0, 72.2, 70.6, 59.1, 30.8, 38.5, 70.0, 73.9, 57.1, 51.7]
before_word_pct = [31.2, 27.4, 24.7, 18.8, 20.0, 21.6, 7.2, 9.9, 15.1, 7.8, 22.4, 8.0, 31.8, 14.7]
after_word_pct  = [99.8, 64.8, 68.4, 69.8, 63.2, 75.2, 67.8, 62.6, 39.2, 39.3, 74.0, 93.0, 69.1, 69.1]

ref_improve = [a - b for a, b in zip(after_ref_pct, before_ref_pct)]
word_improve = [a - b for a, b in zip(after_word_pct, before_word_pct)]

# Color palette
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
# A4/US Letter printable width ~7 inches; ensure all figures stay within this
MAX_WIDTH = 7.5
# Suppress glyph warnings for clean output
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*Glyph.*missing.*")


# ═══════════════════════════════════════════════════════════════
# Chart 1: Before vs After — citation count ratio (grouped bar)
# ═══════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7.5, 3.5))
x = np.arange(len(datasets))
w = 0.35
bars1 = ax.bar(x - w/2, before_ref_pct, w, color=C_BEFORE, edgecolor="white", linewidth=0.5, label="Before (before.md)")
bars2 = ax.bar(x + w/2, after_ref_pct, w, color=C_AFTER, edgecolor="white", linewidth=0.5, label="After (after.md)")
for bar, val in zip(bars1, before_ref_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color="#64748b")
for bar, val in zip(bars2, after_ref_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color=C_AFTER, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=6)
ax.set_ylabel("Citation Count Ratio (%)", fontsize=9)
ax.set_title("Citation Count Ratio: Before vs After Optimization", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 90)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart1_citation_ratio_comparison.png")
plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Chart 2: Before vs After — word content ratio (grouped bar)
# ═══════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7.5, 3.5))
x = np.arange(len(datasets))
w = 0.35
bars1 = ax.bar(x - w/2, before_word_pct, w, color=C_BEFORE, edgecolor="white", linewidth=0.5, label="Before (before.md)")
bars2 = ax.bar(x + w/2, after_word_pct, w, color=C_WORD, edgecolor="white", linewidth=0.5, label="After (after.md)")
for bar, val in zip(bars1, before_word_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color="#64748b")
for bar, val in zip(bars2, after_word_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8, f"{val:.1f}", ha="center", va="bottom", fontsize=5.5, color=C_WORD, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=6)
ax.set_ylabel("Word Content Ratio (%)", fontsize=9)
ax.set_title("Word Content Ratio: Before vs After Optimization", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 110)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart2_word_ratio_comparison.png")
plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Chart 3: Improvement (delta) per dataset — dual line
# ═══════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7.5, 3.2))
x = np.arange(len(datasets))
ax.plot(x, ref_improve, "o-", color=C_REF, linewidth=2, markersize=6, label="Citation Ratio Improvement (pp)")
ax.plot(x, word_improve, "s--", color=C_WORD, linewidth=2, markersize=6, label="Word Ratio Improvement (pp)")
for i in range(len(datasets)):
    ax.annotate(f"{ref_improve[i]:.1f}", (x[i], ref_improve[i]), textcoords="offset points", xytext=(0, 8), fontsize=5.5, ha="center", color=C_REF)
    ax.annotate(f"{word_improve[i]:.1f}", (x[i], word_improve[i]), textcoords="offset points", xytext=(0, -12), fontsize=5.5, ha="center", color=C_WORD)
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=6)
ax.set_ylabel("Improvement (pp)", fontsize=9)
ax.set_title("Optimization Effect: Improvement per Dataset", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart3_improvement_per_dataset.png")
plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Chart 4: Summary — average before/after with annotation
# ═══════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.2))

# Subplot A: Citation ratio
avg_before_ref = np.mean(before_ref_pct)
avg_after_ref = np.mean(after_ref_pct)
axes[0].bar(["Before"], [avg_before_ref], color=C_BEFORE, width=0.4)
axes[0].bar(["After"], [avg_after_ref], color=C_AFTER, width=0.4)
axes[0].text(0, avg_before_ref + 1.5, f"{avg_before_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color="#475569")
axes[0].text(1, avg_after_ref + 1.5, f"{avg_after_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_AFTER)
axes[0].set_ylabel("%", fontsize=9)
axes[0].set_title("Avg Citation Ratio", fontsize=10, fontweight="bold")
axes[0].set_ylim(0, 75)
axes[0].grid(axis="y", alpha=0.3)

# Subplot B: Word ratio
avg_before_word = np.mean(before_word_pct)
avg_after_word = np.mean(after_word_pct)
axes[1].bar(["Before"], [avg_before_word], color=C_BEFORE, width=0.4)
axes[1].bar(["After"], [avg_after_word], color=C_WORD, width=0.4)
axes[1].text(0, avg_before_word + 1.5, f"{avg_before_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color="#475569")
axes[1].text(1, avg_after_word + 1.5, f"{avg_after_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_WORD)
axes[1].set_ylabel("%", fontsize=9)
axes[1].set_title("Avg Word Ratio", fontsize=10, fontweight="bold")
axes[1].set_ylim(0, 85)
axes[1].grid(axis="y", alpha=0.3)

fig.suptitle("Overall Optimization Performance (14 Datasets)", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart4_avg_summary.png")
plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Chart 5: Top 5 best-performing datasets
# ═══════════════════════════════════════════════════════════════
# Rank by sum of ref + word improvement
total_improve = [r + w for r, w in zip(ref_improve, word_improve)]
sorted_idx = np.argsort(total_improve)[::-1]
top5_idx = sorted_idx[:5]

fig, ax = plt.subplots(figsize=(7, 3.2))
x = np.arange(5)
w = 0.3
top5_ref = [ref_improve[i] for i in top5_idx]
top5_word = [word_improve[i] for i in top5_idx]
top5_labels = [topics[i].replace("\n", " ") for i in top5_idx]  # noqa: F821 (defined in outer scope below)
ax.bar(x - w/2, top5_ref, w, color=C_REF, edgecolor="white", label="Citation Ratio Improvement (pp)")
ax.bar(x + w/2, top5_word, w, color=C_WORD, edgecolor="white", label="Word Ratio Improvement (pp)")
for i in range(5):
    ax.text(i - w/2, top5_ref[i] + 1, f"{top5_ref[i]:.1f}", ha="center", fontsize=8, fontweight="bold", color=C_REF)
    ax.text(i + w/2, top5_word[i] + 1, f"{top5_word[i]:.1f}", ha="center", fontsize=8, fontweight="bold", color=C_WORD)
ax.set_xticks(x)
ax.set_xticklabels(top5_labels, fontsize=8)
ax.set_ylabel("Improvement (pp)", fontsize=9)
ax.set_title("Top 5 — Largest Combined Improvement", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart5_top5_improvement.png")
plt.close(fig)


print("5 charts saved to outputs/charts/")
print(f"  chart1_citation_ratio_comparison.png")
print(f"  chart2_word_ratio_comparison.png")
print(f"  chart3_improvement_per_dataset.png")
print(f"  chart4_avg_summary.png")
print(f"  chart5_top5_improvement.png")
