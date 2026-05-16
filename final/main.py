#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from final.adapters.datasets import list_dataset_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="final workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Copy datasets into final/data")
    prepare.add_argument("--dataset", type=int, action="append", dest="datasets")
    prepare.add_argument("--all", action="store_true")
    prepare.add_argument("--force", action="store_true")

    reference = subparsers.add_parser("reference-pool", help="Build reference pool")
    reference.add_argument("--dataset", type=int, required=True)
    reference.add_argument("--refresh-cache", action="store_true")
    reference.add_argument("--refresh-questions", action="store_true")

    generate = subparsers.add_parser("generate-once", help="Generate 5.2 drafts")
    generate.add_argument("--dataset", type=int, required=True)

    citation = subparsers.add_parser("build-citation-drafts", help="Generate 5.3 drafts")
    citation.add_argument("--dataset", type=int, required=True)

    finalize = subparsers.add_parser("finalize", help="Generate final after.md")
    finalize.add_argument("--dataset", type=int, required=True)

    extra = subparsers.add_parser("extra-once", help="Generate one-shot extra coverage_floor draft")
    extra.add_argument("--dataset", type=int, required=True)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate final after.md")
    evaluate.add_argument("--dataset", type=int)
    evaluate.add_argument("--all", action="store_true")

    run_all = subparsers.add_parser("run-all", help="Run the whole workflow for one dataset")
    run_all.add_argument("--dataset", type=int, required=True)
    run_all.add_argument("--force", action="store_true")
    run_all.add_argument("--refresh-cache", action="store_true")
    run_all.add_argument("--refresh-questions", action="store_true")

    competition = subparsers.add_parser("competition", help="Run competition workflow: prepare -> search -> generate -> finalize")
    competition.add_argument("--dataset", type=int)
    competition.add_argument("--all", action="store_true")
    competition.add_argument("--max-workers", type=int, default=4, help="Max parallel datasets when --all (default: 4)")
    competition.add_argument("--refresh-cache", action="store_true")
    competition.add_argument("--refresh-questions", action="store_true")
    return parser.parse_args()


def resolve_datasets(args: argparse.Namespace) -> list[int]:
    if args.all:
        return list_dataset_ids()
    datasets = getattr(args, "datasets", None)
    if datasets:
        return datasets
    if getattr(args, "dataset", None) is not None:
        return [args.dataset]
    raise ValueError("dataset is required")


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        from final.pipeline import step0_prepare

        print(step0_prepare.run(resolve_datasets(args), force=args.force))
        return
    if args.command == "reference-pool":
        from final.pipeline import step1_reference_pool

        print(step1_reference_pool.run(args.dataset, refresh_cache=args.refresh_cache, refresh_questions=args.refresh_questions))
        return
    if args.command == "generate-once":
        from final.pipeline import step2_generate_once

        print(step2_generate_once.run(args.dataset))
        return
    if args.command == "build-citation-drafts":
        from final.pipeline import step2_build_5_3

        print(step2_build_5_3.run(args.dataset))
        return
    if args.command == "finalize":
        from final.pipeline import step3_finalize

        print(step3_finalize.run(args.dataset))
        return
    if args.command == "extra-once":
        from final.pipeline import step3_finalize

        print(step3_finalize.run_extra(args.dataset))
        return
    if args.command == "evaluate":
        from final.pipeline import step4_evaluate

        if args.all:
            print(step4_evaluate.run_batch())
        else:
            print(step4_evaluate.run(args.dataset))
        return
    if args.command == "run-all":
        from final.pipeline import step0_prepare, step1_reference_pool, step2_build_5_3, step2_generate_once, step3_finalize, step4_evaluate

        step0_prepare.run([args.dataset], force=args.force)
        step1_reference_pool.run(args.dataset, refresh_cache=args.refresh_cache, refresh_questions=args.refresh_questions)
        step2_generate_once.run(args.dataset)
        step2_build_5_3.run(args.dataset)
        step3_finalize.run(args.dataset)
        print(step4_evaluate.run(args.dataset))
        return
    if args.command == "competition":
        from final.pipeline import step0_prepare, step1_reference_pool, step2_build_5_3, step2_generate_once, step3_finalize

        dataset_ids = resolve_datasets(args)
        if len(dataset_ids) == 1:
            ds = dataset_ids[0]
            step0_prepare.run([ds], force=True)
            print(f"[{ds} 准备完成]")
            step1_reference_pool.run(ds, refresh_cache=args.refresh_cache, refresh_questions=args.refresh_questions)
            print(f"[{ds} 搜索完成]")
            step2_generate_once.run(ds)
            print(f"[{ds} 5.2 草稿完成]")
            step2_build_5_3.run(ds)
            print(f"[{ds} 5.3 引用稿完成]")
            path = step3_finalize.run(ds)
            print(f"[{ds} 定稿] {path}")
            return

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as time_module

        def _run_one(ds: int) -> str:
            step0_prepare.run([ds], force=True)
            print(f"[{ds} 准备完成]")
            step1_reference_pool.run(ds, refresh_cache=args.refresh_cache, refresh_questions=args.refresh_questions)
            print(f"[{ds} 搜索完成]")
            step2_generate_once.run(ds)
            print(f"[{ds} 5.2 草稿完成]")
            step2_build_5_3.run(ds)
            print(f"[{ds} 5.3 引用稿完成]")
            path = step3_finalize.run(ds)
            return f"[{ds} 定稿] {path}"

        t0 = time_module.time()
        results: list[str] = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {pool.submit(_run_one, ds): ds for ds in dataset_ids}
            for future in as_completed(futures):
                results.append(future.result())
        elapsed = time_module.time() - t0
        for r in results:
            print(r)
        print(f"[全部完成] {len(results)} 个数据集, 耗时 {elapsed:.0f}s")
        return
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
