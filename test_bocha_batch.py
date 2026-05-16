"""
批量测试：对 dataset 202 运行全部 6 种方案，使用博查搜索 + deepseek-v4-pro，
统一搜索关键词，统一复用搜索结果，然后分别评测。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import requests

REPO_ROOT = Path(__file__).resolve().parent
COMPETITION_ROOT = REPO_ROOT / "competition"
COMPETITION_SRC = COMPETITION_ROOT / "src"
for p in (COMPETITION_ROOT, COMPETITION_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import geoplus.pipeline.main as old_pipeline

BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"
BOCHA_API_KEY = os.environ.get("BOCHA_API_KEY")
if not BOCHA_API_KEY:
    raise RuntimeError("BOCHA_API_KEY environment variable is required")
CACHE_DIR = REPO_ROOT / "competition" / "outputs" / "_bocha_search_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BOCHA_KEYWORD_CACHE: dict[str, list[dict]] = {}


def _cache_path(query: str) -> Path:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"bocha_{digest}.json"


def search_web_bocha(query: str, num_results: int = 8) -> list[dict]:
    """博查搜索，跨方案共享缓存。"""
    if query in BOCHA_KEYWORD_CACHE:
        return list(BOCHA_KEYWORD_CACHE[query])

    cache_path = _cache_path(query)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("query") == query and isinstance(cached.get("results"), list):
            BOCHA_KEYWORD_CACHE[query] = list(cached["results"])
            return list(cached["results"])

    payload = {"query": query, "count": num_results, "summary": True}
    try:
        resp = requests.post(
            BOCHA_ENDPOINT,
            headers={"Authorization": f"Bearer {BOCHA_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        print(f"  [!] 博查搜索失败 ({query}): {exc}")
        return []

    rows = (((body.get("data") or {}).get("webPages") or {}).get("value") or [])
    results: list[dict] = []
    for row in rows:
        url = str(row.get("url", "")).strip()
        if not url.startswith("http"):
            continue
        results.append({
            "title": str(row.get("name", "")).strip(),
            "url": url,
            "snippet": str(row.get("snippet", "")).strip()[:300],
        })

    cache_path.write_text(
        json.dumps({"query": query, "results": results, "saved_at": time.time()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    BOCHA_KEYWORD_CACHE[query] = list(results)
    time.sleep(0.3)
    return results


def profile_key_for_variant(variant: str) -> str:
    if variant == "after_nozws":
        return "baseline"
    if variant.startswith("after_"):
        return variant.removeprefix("after_")
    return variant


VARIANTS = [
    "after_nozws",
    "after_dimensions",
    "after_rebuttal",
    "after_rebuttal_extended",
    "after_coverage_floor",
    "after_query_anchored_novelty_gap",
]

# 映射：internal_dataset_id -> legacy_dataset_id (for dataset 202)
LEGACY_DATASET_ID = 102  # dataset 202 对应的 legacy id


def run_variant(variant: str) -> dict:
    """运行一个方案的完整流程，返回结果路径。"""
    profile_key = profile_key_for_variant(variant)
    print(f"\n{'='*60}")
    print(f"  方案: {variant} (profile: {profile_key})")
    print(f"{'='*60}")

    # 先清除该方案的旧缓存（只清 analysis 缓存，保留搜索缓存）
    output_dir = old_pipeline.dataset_output_dir(LEGACY_DATASET_ID)
    cache_root = output_dir / "_cache"
    for f in cache_root.glob(f"flow1_{profile_key}_analysis.md"):
        f.unlink(missing_ok=True)

    # 运行
    os.environ["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
    old_pipeline.search_web = search_web_bocha
    sys.argv = ["main.py", "--dataset", str(LEGACY_DATASET_ID), "--profile", profile_key, "--refresh-cache"]
    old_pipeline.main()

    return {"variant": variant, "profile": profile_key, "dataset": 202}


def evaluate_variant(variant: str) -> dict:
    """评测方案结果。"""
    from final.adapters.evaluator import evaluate_single
    from final.common import REPO_ROOT as FINAL_ROOT

    # 确定输出路径
    output_dir = old_pipeline.dataset_output_dir(LEGACY_DATASET_ID)
    after_path = output_dir / f"{variant}.md"

    if not after_path.exists():
        print(f"  [跳过] {variant}: 输出文件不存在")
        return {"variant": variant, "error": "not_found"}

    print(f"  评测: {after_path.name}")
    result = evaluate_single(202, after_path=after_path)
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  批量测试: dataset 202 × 6 方案 × 博查搜索 + deepseek-v4-pro")
    print("=" * 60)

    # 第一步：全部生成
    for variant in VARIANTS:
        run_variant(variant)

    # 第二步：全部评测
    print(f"\n{'='*60}")
    print("  评测结果")
    print(f"{'='*60}")

    results = {}
    for variant in VARIANTS:
        result = evaluate_variant(variant)
        results[variant] = result

    # 汇总
    print(f"\n{'='*60}")
    print("  汇总")
    print(f"{'='*60}")
    print(f"{'方案':<35} {'总分':>8} {'客观均分':>10} {'主观均分':>10}")
    print("-" * 65)
    for variant in VARIANTS:
        r = results.get(variant)
        if not r or r.get("error"):
            print(f"{variant:<35} {'ERROR':>8}")
            continue
        obj = r.get("result", {}).get("after_objective", {})
        vis = r.get("result", {}).get("after_visibility", {})
        avg_subj = vis.get("aver_subj", 0)
        avg_obj = (obj.get("coverage_ratio", 0) + obj.get("weighted_visibility", 0) + obj.get("position_prominence", 0)) / 3
        total = r.get("summary", {}).get("after_total", 0)
        print(f"{variant:<35} {total:>8.2f} {avg_obj:>10.2f} {avg_subj:>10.2f}")

    print(f"\n{'='*60}")
    print("  七维详细分")
    print(f"{'='*60}")
    dims = ["rele", "infl", "div", "uniq", "clic", "subj_posi", "subj_volu"]
    header = f"{'方案':<35}" + "".join(f"{d:>8}" for d in dims)
    print(header)
    print("-" * (35 + 8 * len(dims)))
    for variant in VARIANTS:
        r = results.get(variant)
        if not r or r.get("error"):
            continue
        vis = r.get("result", {}).get("after_visibility", {})
        scores = "".join(f"{vis.get(d, 0):>8.0f}" for d in dims)
        print(f"{variant:<35}{scores}")
