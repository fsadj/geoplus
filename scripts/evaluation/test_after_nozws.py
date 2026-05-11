#!/usr/bin/env python3
"""Run evaluation for after_nozws.md."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.evaluation.runner import run_evaluation


EXCLUDE_NAMES = {
    "before.md",
    "question.md",
    "after.md",
    "after_nozws.md",
    "after_salient.md",
    "test_before.md",
    "test_after.md",
    "test_after_nozws.md",
    "test_after_salient.md",
    "test_after_r2.md",
    "test_after_nozws_r2.md",
}


def main():
    parser = argparse.ArgumentParser(description="Test after_nozws.md")
    parser.add_argument("--dataset", type=int, default=1, help="Dataset number")
    args = parser.parse_args()
    run_evaluation(
        dataset_id=args.dataset,
        source_name="after_nozws.md",
        output_name="test_after_nozws.md",
        exclude_names=EXCLUDE_NAMES,
        style="square",
        start_message="Testing after_nozws.md (ZWS stripped)...",
    )


if __name__ == "__main__":
    main()
