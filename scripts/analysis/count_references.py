#!/usr/bin/env python3
"""Compare citation stats for before.md vs after.md."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.reference_stats import build_valid_ref_pattern, count_references
from geoplus.paths import dataset_file

VALID_REF_PATTERN = build_valid_ref_pattern(
    "before.md",
    "after.md",
    "test_before.md",
    "test_after.md",
)


def print_stats(result, highlight=None):
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


def main():
    parser = argparse.ArgumentParser(description="引用统计脚本")
    parser.add_argument("--dataset", type=int, default=1, help="数据集编号（默认1）")
    args = parser.parse_args()

    before_stats = count_references(dataset_file(args.dataset, "test_before.md"), VALID_REF_PATTERN)
    after_stats = count_references(dataset_file(args.dataset, "test_after.md"), VALID_REF_PATTERN)

    if before_stats:
        print_stats(before_stats, highlight="before.md")
    if after_stats:
        print_stats(after_stats, highlight="after.md")

    if before_stats and after_stats:
        sep = "=" * 70
        print("\n" + sep)
        print("  关键指标对比（before.md vs after.md）")
        print(sep)

        before_ref_ratio = before_stats["ref_ratio"].get("before.md", 0)
        before_word_ratio = before_stats["ref_word_ratio"].get("before.md", 0)
        after_ref_ratio = after_stats["ref_ratio"].get("after.md", 0)
        after_word_ratio = after_stats["ref_word_ratio"].get("after.md", 0)

        print("\n{:<30} {:>20} {:>20}".format("指标", "修改前(before.md)", "修改后(after.md)"))
        print("-" * 70)
        print("{:<30} {:>19.1f}% {:>19.1f}%".format("引用次数占比", before_ref_ratio, after_ref_ratio))
        print("{:<30} {:>19.1f}% {:>19.1f}%".format("引用内容字数占比", before_word_ratio, after_word_ratio))
        print(
            "\n{:<30} {:>+19.1f}% {:>+19.1f}%".format(
                "提升",
                after_ref_ratio - before_ref_ratio,
                after_word_ratio - before_word_ratio,
            )
        )
        print(sep + "\n")


if __name__ == "__main__":
    main()
