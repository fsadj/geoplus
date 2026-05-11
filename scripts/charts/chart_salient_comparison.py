#!/usr/bin/env python3
"""Generate charts comparing Full-ZWS vs No-ZWS vs Salient-ZWS strategies."""
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

from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()

datasets = list(range(1, 6))
topics = ["DS1\nCognition", "DS2\nHormones", "DS3\nLanguage", "DS4\nMemory", "DS5\nAI & Jobs"]

# From compare_salient.py output
full_cit  = [26.1, 61.3, 50.0, 50.0, 50.0]
full_word = [44.0, 77.1, 62.7, 61.3, 60.0]
nozws_cit  = [44.8, 66.7, 37.0, 68.0, 55.6]
nozws_word = [95.2, 78.1, 51.6, 67.3, 60.9]
salient_cit  = [32.3, 61.1, 53.8, 38.9, 73.1]
salient_word = [71.0, 60.9, 84.1, 47.0, 68.3]

C_FULL = "#3b82f6"
C_NOZWS = "#94a3b8"
C_SALIENT = "#10b981"

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
    "axes.titlesize": 11,
    "axes.labelsize": 9,
    "figure.dpi": 200,
})

# ── Chart: Citation Ratio Comparison (3 strategies) ──
fig, ax = plt.subplots(figsize=(7.5, 3.8))
x = np.arange(len(datasets))
w = 0.25
ax.bar(x - w, full_cit, w, color=C_FULL, edgecolor="white", linewidth=0.5, label="Full-ZWS (after.md)")
ax.bar(x, nozws_cit, w, color=C_NOZWS, edgecolor="white", linewidth=0.5, label="No-ZWS (after_nozws.md)")
ax.bar(x + w, salient_cit, w, color=C_SALIENT, edgecolor="white", linewidth=0.5, label="Salient-ZWS (after_salient.md)")
for i, vals in enumerate(zip(full_cit, nozws_cit, salient_cit)):
    for j, (bar_vals, color) in enumerate([(full_cit, C_FULL), (nozws_cit, C_NOZWS), (salient_cit, C_SALIENT)]):
        ax.text(x[i] + (j-1)*w, bar_vals[i] + 1, f"{bar_vals[i]:.0f}", ha="center", va="bottom", fontsize=5.5, fontweight="bold", color=color)
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=6)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("Citation Ratio: Full-ZWS vs No-ZWS vs Salient-ZWS (DS1-5)", fontsize=11, fontweight="bold")
ax.legend(fontsize=7.5)
ax.set_ylim(0, 105)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_citation.png")
plt.close(fig)

# ── Chart: Density vs Citation Effect ──
fig, ax = plt.subplots(figsize=(6.5, 3.5))

# Density data
strategies = ["No-ZWS", "Salient-ZWS", "Full-ZWS"]
densities = [0, 24.8, 48.0]  # avg densities
avg_cits = [54.4, 51.8, 47.5]
colors = [C_NOZWS, C_SALIENT, C_FULL]

ax.scatter(densities, avg_cits, c=colors, s=200, zorder=5, edgecolors="white", linewidth=1.5)
for i, (d, c, s) in enumerate(zip(densities, avg_cits, strategies)):
    ax.annotate(f"{s}\n({d:.0f}% density, {c:.1f}% cit)", (d, c),
                textcoords="offset points", xytext=(0, 15 if i != 2 else -25),
                ha="center", fontsize=8, fontweight="bold", color=colors[i])

# Trend line
z = np.polyfit(densities, avg_cits, 1)
x_line = np.linspace(-5, 55, 100)
ax.plot(x_line, np.polyval(z, x_line), '--', color="#64748b", alpha=0.6, linewidth=1)

ax.set_xlabel("ZWS Density (%)", fontsize=9)
ax.set_ylabel("Avg Citation Ratio (%)", fontsize=9)
ax.set_title("ZWS Density vs Citation Effectiveness (DS1-5)", fontsize=11, fontweight="bold")
ax.set_xlim(-5, 55)
ax.set_ylim(40, 60)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_density_effect.png")
plt.close(fig)

# ── Chart: Per-dataset improvement of Salient over Full-ZWS ──
fig, ax = plt.subplots(figsize=(7.5, 3.2))
deltas = [s - f for s, f in zip(salient_cit, full_cit)]
colors_d = ["#10b981" if v >= 0 else "#ef4444" for v in deltas]
bars = ax.bar(x, deltas, color=colors_d, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, deltas):
    y_pos = bar.get_height() + 1.5 if val >= 0 else bar.get_height() - 3
    ax.text(bar.get_x() + bar.get_width()/2, y_pos, f"{val:+.1f}pp", ha="center",
            va="bottom" if val >= 0 else "top", fontsize=6, fontweight="bold")
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
mean_d = np.mean(deltas)
ax.axhline(y=mean_d, color=C_SALIENT, linewidth=1, linestyle="--", label=f"Mean: {mean_d:+.1f}pp")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=6)
ax.set_ylabel("Citation Δ (pp)", fontsize=9)
ax.set_title("Salient-ZWS − Full-ZWS: Per-Dataset Citation Improvement", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_vs_full.png")
plt.close(fig)

print("3 charts saved to outputs/charts/:")
print("  chart_salient_citation.png — 3-strategy citation comparison")
print("  chart_salient_density_effect.png — density vs effectiveness")
print("  chart_salient_vs_full.png — salient vs full improvement per dataset")
print(f"\nAvg citation: No-ZWS={np.mean(nozws_cit):.1f}%, Salient={np.mean(salient_cit):.1f}%, Full={np.mean(full_cit):.1f}%")
print(f"Salient vs Full delta: {mean_d:+.1f}pp")
