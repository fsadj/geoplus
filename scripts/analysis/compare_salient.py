#!/usr/bin/env python3
"""Compare Full-ZWS, No-ZWS, and Salient-ZWS strategies."""
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.reference_stats import (
    build_valid_ref_pattern,
    count_references,
    get_target_ratios,
)
from geoplus.paths import dataset_file

VALID_REF_PATTERN = build_valid_ref_pattern(
    "before.md",
    "after.md",
    "after_nozws.md",
    "after_salient.md",
    "test_before.md",
    "test_after.md",
    "test_after_nozws.md",
    "test_after_salient.md",
)


def main():
    datasets = list(range(1, 6))
    topics = ["Cognition", "Hormones", "Language", "Memory", "AI & Jobs"]
    strategies = [
        ("Full-ZWS", "test_after.md", "after.md"),
        ("No-ZWS", "test_after_nozws.md", "after_nozws.md"),
        ("Salient-ZWS", "test_after_salient.md", "after_salient.md"),
    ]

    sep = "=" * 95
    print(f"\n{sep}")
    print("  STRATEGY COMPARISON: Full-ZWS vs No-ZWS vs Salient-ZWS (DS1-5)")
    print(sep)

    results = {label: {"cit": [], "word": []} for label, _, _ in strategies}
    print(f"\n{'DS':<4} {'Topic':<14}", end="")
    for label, _, _ in strategies:
        print(f"  {label:>12}  ", end="")
    print("\n" + "-" * 95)

    for dataset_id in datasets:
        print(f"DS{dataset_id:<3} {topics[dataset_id - 1]:<14}", end="")
        for label, test_file, target_name in strategies:
            stats = count_references(dataset_file(dataset_id, test_file), VALID_REF_PATTERN)
            citation_ratio, word_ratio = get_target_ratios(stats, target_name)
            results[label]["cit"].append(citation_ratio)
            results[label]["word"].append(word_ratio)
            print(f"  {citation_ratio:>6.1f}%/{word_ratio:>5.1f}%", end="")
        print()

    print("\n" + "-" * 95)
    print(f"{'AVERAGE':<18}", end="")
    for label, _, _ in strategies:
        avg_cit = statistics.mean(results[label]["cit"])
        avg_word = statistics.mean(results[label]["word"])
        print(f"  {avg_cit:>6.1f}%/{avg_word:>5.1f}%", end="")
    print()

    print(f"\n{'STRATEGY':<18} {'Avg Cit%':>10} {'Avg Word%':>10} {'vs No-ZWS Δ':>12}")
    print("-" * 55)
    nozws_avg_cit = statistics.mean(results["No-ZWS"]["cit"])
    for label, _, _ in strategies:
        avg_cit = statistics.mean(results[label]["cit"])
        avg_word = statistics.mean(results[label]["word"])
        print(f"  {label:<16} {avg_cit:>9.1f}% {avg_word:>9.1f}% {avg_cit - nozws_avg_cit:>+11.1f}pp")

    best_label, _, _ = max(strategies, key=lambda item: statistics.mean(results[item[0]]["cit"]))
    print(f"\n  Best strategy: {best_label} ({statistics.mean(results[best_label]['cit']):.1f}% avg citation)")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    main()
