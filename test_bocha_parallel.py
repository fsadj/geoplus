"""
并行批量测试：对 dataset 202 运行全部 6 种方案，使用博查搜索 + deepseek-v4-pro。
每个方案启动独立子进程并行运行，所有结果写完后统一评测。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = str(REPO_ROOT / ".venv13" / "bin" / "python")
LEGACY_DATASET_ID = 102  # dataset 202
VARIANTS = [
    "after_nozws",
    "after_dimensions",
    "after_rebuttal",
    "after_rebuttal_extended",
    "after_coverage_floor",
]

PROFILE_MAP = {
    "after_nozws": "baseline",
    "after_dimensions": "dimensions",
    "after_rebuttal": "rebuttal",
    "after_rebuttal_extended": "rebuttal_extended",
    "after_coverage_floor": "coverage_floor",
    "after_query_anchored_novelty_gap": "query_anchored_novelty_gap",
}


def _runner_script(variant: str) -> str:
    profile = PROFILE_MAP[variant]
    api_key = os.environ.get("BOCHA_API_KEY")
    if not api_key:
        raise RuntimeError("BOCHA_API_KEY environment variable is required")
    repo_root_str = str(REPO_ROOT)
    legacy_id = LEGACY_DATASET_ID
    return f'''
import sys, os, hashlib, json, time, requests
from pathlib import Path

sys.path.insert(0, '{repo_root_str}/competition')
sys.path.insert(0, '{repo_root_str}/competition/src')
import geoplus.pipeline.main as old_pipeline

CACHE_DIR = Path(r'{repo_root_str}/competition/outputs/_bocha_search_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"
BOCHA_API_KEY = "{api_key}"

def search_web_bocha(query, num_results=8):
    digest = hashlib.sha1(query.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"bocha_{{digest}}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("query") == query and isinstance(cached.get("results"), list):
            return list(cached["results"])
    payload = {{"query": query, "count": num_results, "summary": True}}
    try:
        resp = requests.post(
            BOCHA_ENDPOINT,
            headers={{"Authorization": f"Bearer {{BOCHA_API_KEY}}", "Content-Type": "application/json"}},
            json=payload, timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        print(f"  [ERROR] 搜索失败: {{exc}}")
        return []
    rows = (((body.get("data") or {{}}).get("webPages") or {{}}).get("value") or [])
    results = []
    for r in rows:
        url = str(r.get("url", "")).strip()
        if not url.startswith("http"):
            continue
        results.append({{
            "title": str(r.get("name", "")).strip(),
            "url": url,
            "snippet": str(r.get("snippet", "")).strip()[:300],
        }})
    cache_path.write_text(
        json.dumps({{"query": query, "results": results, "saved_at": time.time()}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    time.sleep(0.3 + hash(query) % 10 * 0.05)
    return results

os.environ["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
old_pipeline.search_web = search_web_bocha
sys.argv = ["main.py", "--dataset", "{legacy_id}", "--profile", "{profile}", "--refresh-cache"]
old_pipeline.main()
'''


def run_one_variant(variant: str) -> dict:
    profile = PROFILE_MAP[variant]
    output_path = REPO_ROOT / "competition" / "outputs" / "datasets" / str(LEGACY_DATASET_ID) / f"{variant}.md"

    # 删除旧文件，强制重新生成
    if output_path.exists():
        output_path.unlink()
        # 也删除同目录的 _cache 中对应的分析缓存
        cache_dir = output_path.parent / "_cache"
        for f in cache_dir.glob(f"flow1_{profile}_analysis.md"):
            f.unlink(missing_ok=True)

    print(f"[启动] {variant} (profile={profile})")

    runner_code = _runner_script(variant)
    runner_path = REPO_ROOT / f"_run_{variant}.py"
    runner_path.write_text(runner_code)

    env = os.environ.copy()
    env["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
    # 不传 BOCHA_API_KEY 给子进程，已在 runner script 里硬编码

    result = subprocess.run(
        [VENV_PYTHON, str(runner_path)],
        capture_output=True, text=True, timeout=900, env=env
    )
    runner_path.unlink(missing_ok=True)

    if result.returncode != 0:
        # 打印最后几行 stderr
        err_tail = result.stderr.strip()[-500:] if result.stderr.strip() else "no stderr"
        out_tail = result.stdout.strip()[-300:] if result.stdout.strip() else ""
        print(f"[失败] {variant}: {err_tail}")
        if out_tail:
            print(f"  stdout末尾: {out_tail}")
        return {"variant": variant, "status": "failed"}

    size = output_path.stat().st_size if output_path.exists() else 0
    print(f"[完成] {variant} ({size} 字节)")
    return {"variant": variant, "status": "done", "size": size}


def evaluate_all() -> dict:
    sys.path.insert(0, str(REPO_ROOT / "competition"))
    sys.path.insert(0, str(REPO_ROOT / "competition" / "src"))
    from final.adapters.evaluator import evaluate_single

    results = {}
    for variant in VARIANTS:
        output_path = REPO_ROOT / "competition" / "outputs" / "datasets" / str(LEGACY_DATASET_ID) / f"{variant}.md"
        if not output_path.exists():
            print(f"[跳过评测] {variant}: 文件不存在")
            continue
        print(f"[评测] {variant}...")
        r = evaluate_single(202, after_path=output_path)
        results[variant] = r
    return results


def print_results(results: dict):
    print()
    print("=" * 90)
    print("  汇总")
    print("=" * 90)
    header = f"{'方案':<35} {'总分':>8} {'客观均分':>10} {'主观均分':>10} {'覆盖率':>8} {'位置':>8} {'可见性':>8}"
    print(header)
    print("-" * 90)
    for variant in VARIANTS:
        r = results.get(variant)
        if not r:
            print(f"{variant:<35} {'N/A':>8}")
            continue
        obj = r.get("result", {}).get("after_objective", {})
        vis = r.get("result", {}).get("after_visibility", {})
        total = r.get("summary", {}).get("after_total", 0)
        cov = obj.get("coverage_ratio", 0)
        wv = obj.get("weighted_visibility", 0)
        pp = obj.get("position_prominence", 0)
        avg_obj = (cov + wv + pp) / 3
        avg_subj = vis.get("aver_subj", 0)
        print(f"{variant:<35} {total:>8.2f} {avg_obj:>10.2f} {avg_subj:>10.2f} {cov:>8.2f} {pp:>8.2f} {wv:>8.2f}")

    print()
    print("=" * 90)
    print("  七维详细分")
    print("=" * 90)
    dims = ["rele", "infl", "div", "uniq", "clic", "subj_posi", "subj_volu"]
    header = f"{'方案':<35}" + "".join(f"{d:>8}" for d in dims) + f"{'aver_subj':>10}"
    print(header)
    print("-" * (35 + 8 * len(dims) + 10))
    for variant in VARIANTS:
        r = results.get(variant)
        if not r:
            continue
        vis = r.get("result", {}).get("after_visibility", {})
        scores = "".join(f"{vis.get(d, 0):>8.0f}" for d in dims)
        avg = vis.get("aver_subj", 0)
        print(f"{variant:<35}{scores}{avg:>10.2f}")

    print()
    print("=" * 90)
    print("  Judge 评语（前 200 字）")
    print("=" * 90)
    for variant in VARIANTS:
        r = results.get(variant)
        if not r:
            continue
        rationale = r.get("result", {}).get("after_judge", {}).get("rationale", "")
        print(f"\n[{variant}]")
        print(f"  {rationale[:200]}")


if __name__ == "__main__":
    print("=" * 90)
    print("  并行批量测试: dataset 202 × 6 方案 × 博查搜索 + deepseek-v4-pro")
    print("=" * 90)

    # 第一步：并行生成（最多同时跑 3 个，防止 LLM API 过载）
    max_workers = min(3, len(VARIANTS))
    futures = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for v in VARIANTS:
            futures[executor.submit(run_one_variant, v)] = v

        for future in as_completed(futures):
            variant = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[异常] {variant}: {e}")

    print(f"\n{'='*90}")
    print("  全部生成完成，开始评测")
    print(f"{'='*90}")

    # 第二步：评测（串行，耗时不长）
    results = evaluate_all()
    print_results(results)
