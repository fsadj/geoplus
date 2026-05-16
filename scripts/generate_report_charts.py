#!/usr/bin/env python3
"""
为决赛复盘报告生成核心统计图表。
读取 repeated_experiments 中的 JSON 汇总数据，生成 PNG 图表。
已有图表（如 report5_*, chart_*）直接引用，不重复生成。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "competition" / "outputs" / "charts"
REPORT_CHART_DIR = REPO_ROOT / "charts_for_report"
REPORT_CHART_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["PingFang HK", "PingFang SC", "Heiti SC", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"],
    "font.size": 11,
    "axes.unicode_minus": False,
    "figure.dpi": 150,
})


def load_json(path: str) -> dict | list | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def load_jsonl(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------- Chart 1: Route Delta Comparison (Stage 1, 15-simulator avg) ----------
def chart_route_delta_comparison():
    data = load_json(str(REPO_ROOT / "competition" / "outputs" / "repeated_experiments" / "report5_stage1_mechanism_screen" / "summary_by_variant.json"))
    if not data:
        print("[跳过] Chart 1: stage1数据不存在")
        return

    variants = [d["variant"].replace("after_", "") for d in data]
    deltas = [d["avg_delta"] for d in data]
    ci_lows = [d["ci95_low"] for d in data]
    ci_highs = [d["ci95_high"] for d in data]
    obj_deltas = [d["avg_objective_delta"] for d in data]
    ai_deltas = [d["avg_ai_delta"] for d in data]
    variances = [d.get("mean_total_variance", 0) for d in data]
    win_rates = [d.get("win_rate", 0) for d in data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Delta comparison with 95% CI
    x = np.arange(len(variants))
    w = 0.25
    bars1 = ax1.bar(x - w, deltas, w, label="Total Δ", color="#2E86AB", yerr=[[d - l for d, l in zip(deltas, ci_lows)], [h - d for d, h in zip(deltas, ci_highs)]], capsize=4)
    bars2 = ax1.bar(x, obj_deltas, w, label="Objective Δ", color="#A23B72")
    bars3 = ax1.bar(x + w, ai_deltas, w, label="AI Δ", color="#F18F01")

    ax1.set_ylabel("Delta Score")
    ax1.set_title("Route Comparison (5 datasets × 3 simulator)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(variants, rotation=30, ha="right")
    ax1.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3)

    for bar, delta, ci_low in zip(bars1, deltas, ci_lows):
        ax1.text(bar.get_x() + bar.get_width() / 2, ci_low - 1.5, f"{delta:.1f}", ha="center", va="top", fontsize=8, fontweight="bold")

    # Right: Variance + Win Rate (now actually drawn on ax2)
    x2 = np.arange(len(variants))
    w2 = 0.3
    bars_var = ax2.bar(x2, variances, w2, color="#F18F01", alpha=0.7, label="Mean Total Variance")
    ax2.set_ylabel("Mean Total Variance", color="#F18F01")
    ax2.tick_params(axis="y", labelcolor="#F18F01")
    ax2.set_title("Route Variance & Win Rate")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(variants, rotation=30, ha="right")
    ax2.grid(axis="y", alpha=0.3)

    for bar, var in zip(bars_var, variances):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"{var:.1f}", ha="center", fontsize=8, fontweight="bold")

    # Win rate annotations on ax2
    for i, (vr, var) in enumerate(zip(win_rates, variances)):
        color = "#2E86AB" if vr >= 100 else "#A23B72"
        ax2.annotate(f"WR:{vr:.0f}%", (x2[i], variances[i] + 1.5), ha="center", fontsize=9, color=color, fontweight="bold")

    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "route_delta_comparison.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] route_delta_comparison.png")


# ---------- Chart 2: Route Convergence Timeline ----------
def chart_route_convergence():
    """展示各路线在不同实验阶段的 delta 变化：Stage1 → Consensus"""
    stage1 = load_json(str(REPO_ROOT / "competition" / "outputs" / "repeated_experiments" / "report5_stage1_mechanism_screen" / "summary_by_variant.json"))
    consensus = load_json(str(REPO_ROOT / "competition" / "outputs" / "repeated_experiments" / "report5_simulator_consensus_compare" / "summary_by_variant.json"))
    if not stage1 or not consensus:
        print("[跳过] Chart 2: 数据不存在")
        return

    stage1_map = {d["variant"]: d["avg_delta"] for d in stage1}
    consensus_map = {d["variant"]: d["avg_delta"] for d in consensus}

    common = [v for v in stage1_map if v in consensus_map]
    if not common:
        print("[跳过] Chart 2: 无共同路线")
        return

    labels = [v.replace("after_", "") for v in common]
    x = np.arange(len(common))
    w = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    s1_vals = [stage1_map[v] for v in common]
    c_vals = [consensus_map[v] for v in common]

    bars_s1 = ax.bar(x - w / 2, s1_vals, w, label="Stage 1 (avg 3× simulator)", color="#2E86AB")
    bars_c = ax.bar(x + w / 2, c_vals, w, label="Consensus (single round)", color="#F18F01")

    for bar, val in zip(bars_s1, s1_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"{val:.1f}", ha="center", fontsize=8)
    for bar, val in zip(bars_c, c_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"{val:.1f}", ha="center", fontsize=8)

    ax.set_ylabel("Avg Delta")
    ax.set_title("Route Delta: Stage 1 vs Consensus Experiment")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "route_convergence.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] route_convergence.png")


# ---------- Chart 3: Per-Dataset Route Delta Heatmap ----------
def chart_per_dataset_heatmap():
    """读取 raw_results 绘制数据集×路线 delta 热力图"""
    raw = load_jsonl(str(REPO_ROOT / "competition" / "outputs" / "repeated_experiments" / "report5_stage1_mechanism_screen" / "raw_results.jsonl"))
    if not raw:
        print("[跳过] Chart 3: raw_results.jsonl 不存在")
        return

    dataset_map = {}
    for entry in raw:
        ds = str(entry.get("dataset_id", ""))
        variant = entry.get("variant", "").replace("after_", "")
        delta = entry.get("delta", 0)
        if variant not in dataset_map:
            dataset_map[variant] = {}
        dataset_map[variant][ds] = dataset_map[variant].get(ds, []) + [delta]

    variants = sorted(dataset_map.keys())
    datasets = sorted({str(e["dataset_id"]) for e in raw})
    matrix = np.zeros((len(variants), len(datasets)))
    for i, v in enumerate(variants):
        for j, d in enumerate(datasets):
            vals = dataset_map[v].get(d, [0])
            matrix[i, j] = np.mean(vals)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(datasets)))
    ax.set_yticks(np.arange(len(variants)))
    ax.set_xticklabels(datasets)
    ax.set_yticklabels(variants)
    ax.set_title("Per-Dataset Route Delta (mean)")

    for i in range(len(variants)):
        for j in range(len(datasets)):
            val = matrix[i, j]
            color = "white" if val > matrix.max() * 0.6 else "black"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=9, color=color, fontweight="bold")

    fig.colorbar(im, ax=ax, label="Avg Delta")
    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "per_dataset_route_delta.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] per_dataset_route_delta.png")


# ---------- Chart 4: Pipeline Stage Comparison ----------
def chart_pipeline_stages():
    """用已有的 chart 数据展示整体提升：before vs after"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: citation ratio before vs after
    stages = ["Before", "After (No-ZWS Baseline)"]
    citation_ratios = [13.6, 52.9]
    word_ratios = [18.6, 62.7]

    bars = ax1.bar(stages, citation_ratios, color=["#A23B72", "#2E86AB"], width=0.5)
    for bar, val in zip(bars, citation_ratios):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Citation Ratio (%)")
    ax1.set_title("Citation Count Ratio")
    ax1.set_ylim(0, 70)
    ax1.grid(axis="y", alpha=0.3)

    # Right: word ratio
    bars2 = ax2.bar(stages, word_ratios, color=["#A23B72", "#2E86AB"], width=0.5)
    for bar, val in zip(bars2, word_ratios):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Content Word Ratio (%)")
    ax2.set_title("Citation Content Word Ratio")
    ax2.set_ylim(0, 80)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("Overall Pipeline Improvement (14 datasets average)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "pipeline_improvement.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] pipeline_improvement.png")


# ---------- Chart 5: Content Experiment Route Comparison ----------
def chart_content_experiment():
    """从 report5_consensus 数据绘制 consensus vs top routes"""
    consensus = load_json(str(REPO_ROOT / "competition" / "outputs" / "repeated_experiments" / "report5_simulator_consensus_compare" / "summary_by_variant.json"))
    if not consensus:
        print("[跳过] Chart 5: consensus数据不存在")
        return

    # Only keep variants present in consensus
    variant_order = ["after_simulator_consensus", "after_query_anchored_novelty_gap", "after_rebuttal", "after_coverage_floor", "after_nozws"]
    data_map = {d["variant"]: d for d in consensus}
    plot_data = [(v, data_map[v]) for v in variant_order if v in data_map]

    if not plot_data:
        print("[跳过] Chart 5: 无匹配路线")
        return

    labels = [v.replace("after_", "") for v, _ in plot_data]
    deltas = [d["avg_delta"] for _, d in plot_data]
    ci_lows = [d["ci95_low"] for _, d in plot_data]
    ci_highs = [d["ci95_high"] for _, d in plot_data]
    obj_deltas = [d["avg_objective_delta"] for _, d in plot_data]
    ai_deltas = [d["avg_ai_delta"] for _, d in plot_data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(labels))
    w = 0.25

    # Left: Total delta with CI
    bars = ax1.bar(x, deltas, w * 2, color="#2E86AB", yerr=[[d - l for d, l in zip(deltas, ci_lows)], [h - d for d, h in zip(deltas, ci_highs)]], capsize=4)
    for bar, val in zip(bars, deltas):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5, f"{val:.1f}", ha="center", fontsize=9, fontweight="bold")
    ax1.set_ylabel("Total Delta")
    ax1.set_title("Consensus Experiment: Total Δ with 95% CI")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=25, ha="right")
    ax1.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax1.grid(axis="y", alpha=0.3)

    # Right: Objective vs AI delta stacked
    bars_obj = ax2.bar(x - w / 2, obj_deltas, w, label="Objective Δ", color="#A23B72")
    bars_ai = ax2.bar(x + w / 2, ai_deltas, w, label="AI Δ", color="#F18F01")
    ax2.set_ylabel("Delta")
    ax2.set_title("Objective Δ vs AI Δ")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=25, ha="right")
    ax2.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax2.legend()
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("Final Route Comparison (5 competition datasets)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "consensus_route_comparison.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] consensus_route_comparison.png")


# ---------- Chart 6: 3-round stability (from report3 curated naturalized) ----------
def chart_stability():
    data = load_json(str(REPO_ROOT / "competition" / "outputs" / "report3_curated_naturalized_3round_summary.json"))
    if not data:
        print("[跳过] Chart 6: 3-round 数据不存在")
        return

    if isinstance(data, dict):
        data = data.get("variants", [])

    variants = [d["variant"].replace("after_", "") for d in data]
    deltas = [d.get("avg_delta", 0) for d in data]
    ranges = [d.get("delta_range", 0) for d in data]
    win_rates = [d.get("win_rate", 0) for d in data]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(variants))
    w = 0.3

    bars = ax.bar(x, deltas, w, color="#2E86AB")
    ax.errorbar(x, deltas, yerr=[[0] * len(deltas), [r / 2 for r in ranges]], fmt="none", color="gray", capsize=4, capthick=1.5)

    for bar, val, wr in zip(bars, deltas, win_rates):
        color = "#2E86AB" if wr >= 100 else "#A23B72"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5, f"Δ={val:.1f}\nWR={wr:.0f}%", ha="center", fontsize=8, color=color, fontweight="bold")

    ax.set_ylabel("3-Round Avg Delta")
    ax.set_title("3-Round Stability Test (DS101-103, curated)")
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right")
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(REPORT_CHART_DIR / "stability_3round.png"), bbox_inches="tight")
    plt.close(fig)
    print("[生成] stability_3round.png")


# ---------- Main ----------
def main():
    print("=" * 60)
    print("生成决赛复盘报告统计图表")
    print("=" * 60)

    chart_route_delta_comparison()
    chart_route_convergence()
    chart_per_dataset_heatmap()
    chart_pipeline_stages()
    chart_content_experiment()
    chart_stability()

    print(f"\n全部完成！图表已输出至: {REPORT_CHART_DIR}")
    print("可用图表:")
    for f in sorted(REPORT_CHART_DIR.glob("*.png")):
        print(f"  {f.name}")

if __name__ == "__main__":
    main()
