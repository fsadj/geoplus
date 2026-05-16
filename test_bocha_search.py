"""
临时测试脚本：将旧 pipeline 的 SearXNG 搜索替换为博查 API，
保持 ~12 个关键词、~90-96 条结果的结构不变，测试 deepseek-v4-pro 下的分数。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

# 添加路径，使导入正常工作
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


def _search_cache_path(query: str) -> Path:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"bocha_{digest}.json"


def search_web_bocha(query: str, num_results: int = 8) -> list[dict]:
    """博查 API 搜索，替代旧 pipeline 的 SearXNG search_web。"""
    cache_path = _search_cache_path(query)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("query") == query and isinstance(cached.get("results"), list):
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
    time.sleep(0.3)
    return results


if __name__ == "__main__":
    # 注入博查搜索替换 SearXNG
    old_pipeline.search_web = search_web_bocha

    # 设置模型为 deepseek-v4-pro
    os.environ["ANTHROPIC_MODEL"] = "deepseek-v4-pro"

    # 运行旧 pipeline
    sys.argv = ["main.py", "--dataset", "101", "--profile", "coverage_floor", "--refresh-cache"]
    old_pipeline.main()
