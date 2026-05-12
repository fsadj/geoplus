#!/usr/bin/env python3
"""Run evaluation for after.md."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.evaluation.runner import run_evaluation
from geoplus.evaluation.specs import build_test_output_name, get_evaluation_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Test after.md")
    parser.add_argument("--dataset", type=int, default=1, help="Dataset number")
    args = parser.parse_args()

    spec = get_evaluation_spec("after")
    run_evaluation(
        dataset_id=args.dataset,
        source_name=spec.source_name,
        output_name=build_test_output_name("after", 1),
        style=spec.style,
        start_message=spec.start_message,
        missing_message=spec.missing_message,
    )


if __name__ == "__main__":
    main()
