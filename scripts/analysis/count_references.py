#!/usr/bin/env python3
"""Compare citation stats for before.md vs a chosen optimized variant."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import load_eval_stats
from geoplus.analysis.reference_stats import get_target_ratios
from geoplus.evaluation.specs import EVALUATION_SPECS, get_evaluation_spec


VARIANT_CHOICES = sorted(variant_key for variant_key in EVALUATION_SPECS if variant_key != "before")


def print_stats(result: dict, highlight: str | None = None) -> None:
    sep = "=" * 70
    print("\n" + sep)
    print("  文件:", result["file"])
    print("  总引用次数:", result["total_ref"])
    print("  总字数:", result["total_words"])
    print(sep)

    sorted_refs = sorted(result["ref_count"].items(), key=lambda item: item[1], reverse=True)
    print("\n引用文档            次数   次数占比      字数   字数占比")
    print("-" * 70)
    for ref, count in sorted_refs:
        ratio = result["ref_ratio"].get(ref, 0)
        words = result["ref_words"].get(ref, 0)
        word_ratio = result["ref_word_ratio"].get(ref, 0)
        prefix = "-> " if ref == highlight else "   "
        line = "{}{:<20} {:>4} {:>9.1f}% {:>8} {:>11.1f}%".format(
            prefix, ref, count, ratio, words, word_ratio
        )
        print(line)
    print(sep + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="引用统计脚本")
    parser.add_argument("--dataset", type=int, default=1, help="数据集编号（默认1）")
    parser.add_argument(
        "--variant",
        choices=VARIANT_CHOICES,
        default="after_nozws",
        help="对比的优化版本（默认 after_nozws）",
    )
    args = parser.parse_args()

    before_spec = get_evaluation_spec("before")
    compare_spec = get_evaluation_spec(args.variant)
    before_stats = load_eval_stats(args.dataset, "before", 1)
    compare_stats = load_eval_stats(args.dataset, args.variant, 1)

    if before_stats:
        print_stats(before_stats, highlight=before_spec.target_ref_name)
    if compare_stats:
        print_stats(compare_stats, highlight=compare_spec.target_ref_name)

    if before_stats and compare_stats:
        sep = "=" * 70
        before_ref_ratio, before_word_ratio = get_target_ratios(before_stats, before_spec.target_ref_name)
        compare_ref_ratio, compare_word_ratio = get_target_ratios(compare_stats, compare_spec.target_ref_name)

        print("\n" + sep)
        print(f"  关键指标对比（{before_spec.source_name} vs {compare_spec.source_name}）")
        print(sep)
        print(
            "\n{:<30} {:>20} {:>20}".format(
                "指标",
                f"修改前({before_spec.source_name})",
                f"修改后({compare_spec.source_name})",
            )
        )
        print("-" * 70)
        print("{:<30} {:>19.1f}% {:>19.1f}%".format("引用次数占比", before_ref_ratio, compare_ref_ratio))
        print("{:<30} {:>19.1f}% {:>19.1f}%".format("引用内容字数占比", before_word_ratio, compare_word_ratio))
        print(
            "\n{:<30} {:>+19.1f}% {:>+19.1f}%".format(
                "提升",
                compare_ref_ratio - before_ref_ratio,
                compare_word_ratio - before_word_ratio,
            )
        )
        print(sep + "\n")


if __name__ == "__main__":
    main()
