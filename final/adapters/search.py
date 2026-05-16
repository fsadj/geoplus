from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from final.adapters.datasets import load_baseline_answer, load_docs, load_manifest, load_question_groups, load_question_lines, save_question_groups, save_question_text, workspace_dir
from final.common import WORKSPACE_ROOT, call_with_retry, fetch_url, load_gpt_client, load_json, parse_question_lines, read_optional_text, short_slug, timestamp, write_json, write_text
from final.prompts import CLEAN_RESULTS_SYSTEM_PROMPT, QUESTION_SYSTEM_PROMPT, build_clean_results_user_prompt, build_question_user_prompt

BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"

def _bocha_api_key() -> str:
    key = os.environ.get("BOCHA_API_KEY")
    if not key:
        raise RuntimeError("BOCHA_API_KEY environment variable is required")
    return key


def _shared_cache_dir() -> Path:
    path = WORKSPACE_ROOT / "shared_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _search_cache_path(query: str) -> Path:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return _shared_cache_dir() / f"bocha_search_{digest}.json"


def _fetch_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return _shared_cache_dir() / f"fetch_{digest}.json"


def _extract_json_array(text: str) -> list[dict[str, str]]:
    stripped = text.strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, str]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append({str(key): str(value) for key, value in item.items()})
    return rows


def _extract_question_groups(text: str) -> list[dict[str, object]]:
    stripped = text.strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    groups: list[dict[str, object]] = []
    if start >= 0 and end >= start:
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                aliases_raw = item.get("aliases", [])
                if not question:
                    continue
                aliases: list[str] = []
                if isinstance(aliases_raw, list):
                    for alias in aliases_raw:
                        normalized = str(alias).strip()
                        if normalized and normalized != question and normalized not in aliases:
                            aliases.append(normalized)
                groups.append({"question": question, "aliases": aliases[:2]})
    return groups


def _fallback_question_groups(lines: list[str]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for index in range(0, len(lines), 3):
        chunk = lines[index : index + 3]
        if not chunk:
            continue
        question = chunk[0]
        aliases = [line for line in chunk[1:] if line != question]
        groups.append({"question": question, "aliases": aliases[:2]})
    return groups


def _merge_question_groups(main_question: str | None, generated_groups: list[dict[str, object]], existing_lines: list[str], title: str) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen_questions: set[str] = set()

    if main_question:
        first_aliases: list[str] = []
        for group in generated_groups:
            candidates = [str(group.get("question", "")).strip()] + [str(alias).strip() for alias in group.get("aliases", []) if str(alias).strip()]
            for candidate in candidates:
                if candidate and candidate != main_question and candidate not in first_aliases:
                    first_aliases.append(candidate)
                if len(first_aliases) >= 2:
                    break
            if len(first_aliases) >= 2:
                break
        merged.append({"question": main_question, "aliases": first_aliases[:2]})
        seen_questions.add(main_question)

    for group in generated_groups:
        question = str(group.get("question", "")).strip()
        if not question or question in seen_questions:
            continue
        aliases = [str(alias).strip() for alias in group.get("aliases", []) if str(alias).strip() and str(alias).strip() != question]
        deduped_aliases: list[str] = []
        for alias in aliases:
            if alias not in deduped_aliases:
                deduped_aliases.append(alias)
        merged.append({"question": question, "aliases": deduped_aliases[:2]})
        seen_questions.add(question)
        if len(merged) >= 5:
            break

    for line in existing_lines:
        if line in seen_questions:
            continue
        merged.append({"question": line, "aliases": []})
        seen_questions.add(line)
        if len(merged) >= 5:
            break

    if not merged and title:
        merged.append({"question": title, "aliases": []})
    while len(merged) < 5 and merged:
        seed = merged[min(len(merged) - 1, 2)]
        merged.append({"question": str(seed["question"]), "aliases": list(seed.get("aliases", []))})
    return merged[:5]


def generate_question_groups(dataset_id: int, *, refresh: bool = False) -> list[dict[str, object]]:
    existing_groups = load_question_groups(dataset_id)
    if existing_groups and len(existing_groups) >= 5 and not refresh:
        return existing_groups[:5]

    existing_lines = load_question_lines(dataset_id)
    main_question = existing_lines[0] if existing_lines else None
    docs = load_docs(dataset_id)
    baseline_answer = load_baseline_answer(dataset_id)
    config, client = load_gpt_client()
    generated = call_with_retry(
        client,
        model=config.answer_model,
        system=QUESTION_SYSTEM_PROMPT,
        user=build_question_user_prompt(main_question, docs, baseline_answer),
        max_tokens=1600,
    )
    generated_groups = _extract_question_groups(generated)
    if not generated_groups:
        generated_groups = _fallback_question_groups(parse_question_lines(generated))

    title = str(load_manifest(dataset_id).get("title", "")).strip()
    merged = _merge_question_groups(main_question, generated_groups, existing_lines, title)
    save_question_groups(dataset_id, merged)
    save_question_text(dataset_id, [str(group["question"]).strip() for group in merged])
    return merged


def generate_question_lines(dataset_id: int, *, refresh: bool = False) -> list[str]:
    return [str(group["question"]).strip() for group in generate_question_groups(dataset_id, refresh=refresh)]


def search_bocha(query: str, *, count: int = 5, refresh_cache: bool = False) -> list[dict]:
    cache_path = _search_cache_path(query)
    cached = load_json(cache_path)
    if isinstance(cached, dict) and cached.get("query") == query and isinstance(cached.get("results"), list) and not refresh_cache:
        return cached["results"]

    api_key = _bocha_api_key()

    payload = {"query": query, "count": count, "summary": True}
    response = requests.post(
        BOCHA_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    rows = (((body.get("data") or {}).get("webPages") or {}).get("value") or [])
    results: list[dict] = []
    for row in rows:
        url = str(row.get("url", "")).strip()
        if not url.startswith("http"):
            continue
        results.append(
            {
                "title": str(row.get("name", "")).strip(),
                "url": url,
                "snippet": str(row.get("snippet", "")).strip()[:260],
                "summary": str(row.get("summary", "")).strip()[:260],
                "site_name": str(row.get("siteName", "")).strip(),
                "domain": (urlparse(url).hostname or "").lower(),
            }
        )
    write_json(cache_path, {"query": query, "results": results, "saved_at": timestamp()})
    time.sleep(0.2)
    return results


def clean_candidates(question_lines: list[str], raw_candidates: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    config, client = load_gpt_client()
    cleaned = call_with_retry(
        client,
        model=config.answer_model,
        system=CLEAN_RESULTS_SYSTEM_PROMPT,
        user=build_clean_results_user_prompt(question_lines, raw_candidates),
        max_tokens=2400,
    )
    keep_rows = _extract_json_array(cleaned)
    keep_by_url = {row.get("url", ""): row for row in keep_rows if row.get("url")}
    ordered_unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw_candidates:
        url = row["url"]
        if url in seen:
            continue
        seen.add(url)
        ordered_unique.append(row)

    available: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for row in ordered_unique:
        url = row["url"]
        if url in keep_by_url:
            available.append({**row, "reason": keep_by_url[url].get("reason", "")})
        else:
            rejected.append({**row, "reason": "llm_filtered"})

    minimum_keep = min(20, len(ordered_unique))
    maximum_keep = min(30, len(ordered_unique))
    if len(available) < minimum_keep:
        available_urls = {row["url"] for row in available}
        for row in ordered_unique:
            if row["url"] in available_urls:
                continue
            available.append({**row, "reason": "fallback_topup"})
            available_urls.add(row["url"])
            if len(available) >= minimum_keep:
                break
    if len(available) > maximum_keep:
        trimmed = available[maximum_keep:]
        rejected.extend({**row, "reason": row.get("reason", "trimmed_over_limit")} for row in trimmed)
        available = available[:maximum_keep]

    kept_urls = {row["url"] for row in available}
    final_rejected: list[dict[str, str]] = []
    seen_rejected: set[str] = set()
    for row in rejected:
        url = row["url"]
        if url in kept_urls or url in seen_rejected:
            continue
        seen_rejected.add(url)
        final_rejected.append(row)
    return available, final_rejected


def fetch_reference_doc(url: str, *, refresh_cache: bool = False) -> str:
    cache_path = _fetch_cache_path(url)
    cached = load_json(cache_path)
    if isinstance(cached, dict) and cached.get("url") == url and isinstance(cached.get("content"), str) and not refresh_cache:
        return str(cached.get("content", ""))
    content = fetch_url(url)
    write_json(cache_path, {"url": url, "content": content, "saved_at": timestamp()})
    return content


def build_reference_pool(dataset_id: int, *, refresh_cache: bool = False, refresh_questions: bool = False) -> dict:
    question_lines = generate_question_lines(dataset_id, refresh=refresh_questions)
    workspace = workspace_dir(dataset_id) / "reference_pool"
    refs_dir = workspace / "refs"
    workspace.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    raw_candidates: list[dict[str, str]] = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _search_one(question: str) -> list[dict[str, str]]:
        try:
            results: list[dict[str, str]] = []
            for row in search_bocha(question, count=5, refresh_cache=refresh_cache):
                results.append(
                    {
                        "question": question,
                        "title": str(row.get("title", "")),
                        "url": str(row.get("url", "")),
                        "snippet": str(row.get("snippet", "")),
                        "summary": str(row.get("summary", "")),
                        "domain": str(row.get("domain", "")),
                    }
                )
            return results
        except Exception as exc:
            print(f"  [搜索跳过] 问题 '{question[:30]}': {exc}")
            return []

    with ThreadPoolExecutor(max_workers=min(len(question_lines) or 1, 5)) as pool:
        futures = {pool.submit(_search_one, q): q for q in question_lines}
        for future in as_completed(futures):
            raw_candidates.extend(future.result())

    available_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []
    if raw_candidates:
        try:
            available_rows, rejected_rows = clean_candidates(question_lines, raw_candidates)
        except Exception as exc:
            print(f"  [候选清洗跳过]: {exc}")
            rejected_rows = [{**r, "reason": "llm_error"} for r in raw_candidates]

    def _fetch_one(args: tuple[int, dict]) -> dict | None:
        index, row = args
        try:
            content = fetch_reference_doc(row["url"], refresh_cache=refresh_cache)
        except Exception as exc:
            rejected_rows.append({**row, "reason": f"fetch_error: {exc}"})
            return None
        if len(content.strip()) < 200:
            rejected_rows.append({**row, "reason": "empty_content"})
            return None
        file_name = f"{index:02d}-{short_slug(row['title'] or row['url'])}.md"
        write_text(refs_dir / file_name, content)
        return {**row, "content": content, "file": file_name}

    to_fetch = list(enumerate(available_rows, start=1))
    available_docs: list[dict[str, str]] = []
    if to_fetch:
        with ThreadPoolExecutor(max_workers=min(len(to_fetch), 8)) as pool:
            for result in pool.map(_fetch_one, to_fetch):
                if result is not None:
                    available_docs.append(result)

    payload = {
        "dataset_id": dataset_id,
        "question_lines": question_lines,
        "search_count": len(raw_candidates),
        "available_count": len(available_docs),
        "rejected_count": len(rejected_rows),
        "available_docs": available_docs,
        "rejected": rejected_rows,
        "saved_at": timestamp(),
    }
    write_json(workspace / "search_payload.json", payload)
    write_json(workspace / "available.json", available_docs)
    write_json(workspace / "rejected.json", rejected_rows)
    return payload


def load_reference_pool(dataset_id: int) -> dict:
    workspace = workspace_dir(dataset_id) / "reference_pool" / "search_payload.json"
    payload = load_json(workspace)
    if not isinstance(payload, dict):
        raise ValueError(f"reference pool missing for dataset {dataset_id}")
    return payload
