#!/usr/bin/env python3
"""Compare Full-ZWS, No-ZWS, and Salient-ZWS strategies."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import summarize_salient_comparison


def main() -> None:
    summary = summarize_salient_comparison()
    labels = summary["labels"]
    strategies = [
        ("Full-ZWS", summary["full_cit"], summary["full_word"]),
        ("No-ZWS", summary["nozws_cit"], summary["nozws_word"]),
        ("Salient-ZWS", summary["salient_cit"], summary["salient_word"]),
    ]

    sep = "=" * 95
    print(f"\n{sep}")
    print("  STRATEGY COMPARISON: Full-ZWS vs No-ZWS vs Salient-ZWS")
    print(sep)

    print(f"\n{'DS':<6}", end="")
    for label, _, _ in strategies:
        print(f"  {label:>12}  ", end="")
    print("\n" + "-" * 95)

    for index, dataset_label in enumerate(labels):
        print(f"{dataset_label:<6}", end="")
        for _, citation_series, word_series in strategies:
            print(f"  {citation_series[index]:>6.1f}%/{word_series[index]:>5.1f}%", end="")
        print()

    print("\n" + "-" * 95)
    print(f"{'AVERAGE':<18}", end="")
    for strategy_label in ["Full-ZWS", "No-ZWS", "Salient-ZWS"]:
        metrics = summary["strategy_summary"][strategy_label]
        print(f"  {metrics['avg_cit']:>6.1f}%/{metrics['avg_word']:>5.1f}%", end="")
    print()

    print(f"\n{'STRATEGY':<18} {'Avg Cit%':>10} {'Avg Word%':>10} {'vs No-ZWS Δ':>12}")
    print("-" * 55)
    nozws_avg_cit = summary["strategy_summary"]["No-ZWS"]["avg_cit"]
    for strategy_label in ["Full-ZWS", "No-ZWS", "Salient-ZWS"]:
        metrics = summary["strategy_summary"][strategy_label]
        print(
            f"  {strategy_label:<16} {metrics['avg_cit']:>9.1f}% {metrics['avg_word']:>9.1f}% "
            f"{metrics['avg_cit'] - nozws_avg_cit:>+11.1f}pp"
        )

    best_label = max(summary["strategy_summary"], key=lambda name: summary["strategy_summary"][name]["avg_cit"])
    print(f"\n  Best strategy: {best_label} ({summary['strategy_summary'][best_label]['avg_cit']:.1f}% avg citation)")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    main()
