from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import ContestItem, ProvidedVisibilityScore, SourceDocument


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = PROJECT_ROOT / "data" / "baseline"
OUTPUTS_ROOT = PROJECT_ROOT / "outputs" / "datasets"
TRAILING_COMMA_RE = re.compile(r",(?=\s*[}\]])")
SCORE_FIELD_ALIASES = {
    "word_volu": ("word_volu",),
    "posi_prom": ("posi_prom",),
    "word_posi": ("word_posi",),
    "rele": ("rele",),
    "infl": ("infl",),
    "div": ("div", "dive"),
    "uniq": ("uniq",),
    "clic": ("clic",),
    "subj_posi": ("subj_posi", "sub_posi"),
    "subj_volu": ("subj_volu", "sub_volu"),
    "aver_subj": ("aver_subj",),
    "final_score": ("final_score",),
}


def baseline_dir(dataset_id: int) -> Path:
    return BASELINE_ROOT / str(dataset_id)


def outputs_dir(dataset_id: int) -> Path:
    return OUTPUTS_ROOT / str(dataset_id)


def _read_required(path: Path, *, strip: bool = True) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    return text.strip() if strip else text


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{field_name} must be an integer")


def _extract_score_field(payload: dict[str, Any], canonical_name: str, aliases: tuple[str, ...]) -> float:
    present: dict[str, float] = {}
    for key in aliases:
        if key in payload:
            present[key] = float(payload[key])
    if not present:
        raise ValueError(f"待优化文本的可见性分数缺少字段: {canonical_name}")
    if len({round(value, 6) for value in present.values()}) > 1:
        alias_list = ", ".join(present)
        raise ValueError(f"待优化文本的可见性分数字段冲突: {alias_list}")
    return next(iter(present.values()))


def _normalize_visibility_score(raw_score: Any) -> ProvidedVisibilityScore:
    if not isinstance(raw_score, dict):
        raise ValueError("待优化文本的可见性分数 must be an object")
    normalized = {
        field_name: _extract_score_field(raw_score, field_name, aliases)
        for field_name, aliases in SCORE_FIELD_ALIASES.items()
    }
    return ProvidedVisibilityScore(**normalized)


def _build_contest_item(payload: dict[str, Any], *, item_id: str) -> ContestItem:
    required_keys = ("用户查询", "文本列表", "待优化文本的序号", "生成的原始答案", "待优化文本的可见性分数")
    missing_keys = [key for key in required_keys if key not in payload]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"题目 JSON 缺少必填字段: {missing}")

    query = _require_non_empty_text(payload.get("用户查询"), "用户查询")
    raw_texts = payload.get("文本列表")
    if not isinstance(raw_texts, list) or len(raw_texts) != 5:
        raise ValueError("文本列表 must contain exactly 5 items")

    texts: list[SourceDocument] = []
    seen_source_ids: set[int] = set()
    for index, raw_doc in enumerate(raw_texts, start=1):
        if not isinstance(raw_doc, dict):
            raise ValueError(f"文本列表[{index}] must be an object")
        source_id = _require_int(raw_doc.get("文本序号"), f"文本列表[{index}].文本序号")
        if source_id in seen_source_ids:
            raise ValueError(f"文本序号 duplicated: {source_id}")
        seen_source_ids.add(source_id)

        search_rank = _require_int(
            raw_doc.get("位于传统搜索引擎搜索答案列表的位次"),
            f"文本列表[{index}].位于传统搜索引擎搜索答案列表的位次",
        )
        url = _require_non_empty_text(raw_doc.get("url链接"), f"文本列表[{index}].url链接")
        title = _require_non_empty_text(raw_doc.get("标题"), f"文本列表[{index}].标题")
        content = _require_non_empty_text(raw_doc.get("内容"), f"文本列表[{index}].内容")
        texts.append(
            SourceDocument(
                source_id=source_id,
                label=f"文本{source_id}",
                title=title,
                content=content,
                url=url,
                search_rank=search_rank,
            )
        )

    target_source_id = _require_int(payload.get("待优化文本的序号"), "待优化文本的序号")
    if target_source_id not in seen_source_ids:
        raise ValueError("待优化文本的序号 must match one 文本序号")
    target_index = next(index for index, doc in enumerate(texts) if doc.source_id == target_source_id)

    generated_original_answer = _require_non_empty_text(payload.get("生成的原始答案"), "生成的原始答案")
    visibility_before = _normalize_visibility_score(payload.get("待优化文本的可见性分数"))
    return ContestItem(
        item_id=item_id,
        query=query,
        texts=texts,
        target_index=target_index,
        generated_original_answer=generated_original_answer,
        visibility_before=visibility_before,
    )


def parse_json_item_text(raw_text: str, *, item_id: str, input_mode: str = "strict") -> ContestItem:
    if input_mode not in {"strict", "compat"}:
        raise ValueError(f"Unsupported input_mode: {input_mode}")
    normalized_text = raw_text.strip()
    if input_mode == "compat":
        normalized_text = TRAILING_COMMA_RE.sub("", normalized_text)
    payload = json.loads(normalized_text)
    if not isinstance(payload, dict):
        raise ValueError("题目 JSON 顶层必须是对象")
    return _build_contest_item(payload, item_id=item_id)


def load_json_item(item_path: str | Path, *, input_mode: str = "strict") -> ContestItem:
    path = Path(item_path)
    raw_text = _read_required(path, strip=False)
    return parse_json_item_text(raw_text, item_id=path.stem, input_mode=input_mode)


def load_markdown_item(dataset_id: int, *, target_path: Path | None = None, target_label: str | None = None) -> ContestItem:
    base = baseline_dir(dataset_id)
    query = _read_required(base / "question.md")
    before_text = _read_required(base / "before.md")

    target_content = before_text
    target_file_label = target_label or "before.md"
    if target_path is not None:
        target_content = _read_required(target_path)
        target_file_label = target_label or target_path.name

    texts = [
        SourceDocument(
            source_id=1,
            label=target_file_label,
            title=target_file_label,
            content=target_content,
            url=f"dataset://{dataset_id}/target",
            search_rank=1,
        )
    ]
    for offset, name in enumerate(("1.md", "2.md", "3.md", "4.md"), start=2):
        file_path = base / name
        texts.append(
            SourceDocument(
                source_id=offset,
                label=name,
                title=name,
                content=_read_required(file_path),
                url=f"dataset://{dataset_id}/{name}",
                search_rank=offset,
            )
        )

    return ContestItem(item_id=f"DS{dataset_id}", query=query, texts=texts, target_index=0)


def resolve_after_path(dataset_id: int, after_name: str | None = None, after_path: str | None = None) -> Path | None:
    if after_path:
        return Path(after_path)
    if after_name:
        return outputs_dir(dataset_id) / after_name
    return None


def parse_dataset_ids(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def parse_path_list(raw: str) -> list[Path]:
    return [Path(part.strip()) for part in raw.split(",") if part.strip()]
