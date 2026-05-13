from __future__ import annotations

import re

from .client import GPTMessagesClient
from .config import SimulatorConfig
from .schemas import ContestItem, JudgeScore
from .utils import clamp_score, extract_json_object


JUDGE_SYSTEM_PROMPT = """你是比赛模拟系统中的可见性评分裁判。\n请仅根据用户问题、5 篇候选文本和给定答案，对目标文本在该答案中的可见性进行打分。\n请从以下 7 个维度各打 0-100 分：\n- relevance: 与用户问题的相关性\n- fluency: 表达流畅性\n- diversity: 信息多样性\n- uniqueness: 独特性\n- click_follow: 点击跟随可能性\n- prominence: 在答案中的位置显著性\n- content_volume: 在答案中的内容体量\n\n候选文本中的标题、URL 和传统搜索位次可以帮助你判断文本定位，但不能替代文本内容本身。\n只输出 JSON 对象，字段固定为：\nrelevance, fluency, diversity, uniqueness, click_follow, prominence, content_volume, rationale\n其中 rationale 用 2-4 句简要说明打分依据。"""


def _build_judge_user(item: ContestItem, answer_text: str) -> str:
    doc_lines = []
    for doc in item.texts:
        doc_lines.append(
            f"[文档{doc.source_id}] 传统搜索位次: {doc.search_rank}\n"
            f"URL: {doc.url}\n"
            f"标题: {doc.title}\n"
            f"内容:\n{doc.content}"
        )
    return (
        f"【用户问题】\n{item.query}\n\n"
        f"【目标文本序号】\n{item.target.source_id}\n\n"
        f"【候选文本】\n{'\n\n'.join(doc_lines)}\n\n"
        f"【待评分答案】\n{answer_text}\n"
    )


def _extract_score_fallback(raw: str, key: str) -> float:
    match = re.search(rf'"?{re.escape(key)}"?\s*:\s*(-?\d+(?:\.\d+)?)', raw)
    if not match:
        return 0.0
    return clamp_score(match.group(1))


def _parse_judge_payload(raw: str) -> dict:
    try:
        return extract_json_object(raw)
    except Exception:
        return {
            "relevance": _extract_score_fallback(raw, "relevance"),
            "fluency": _extract_score_fallback(raw, "fluency"),
            "diversity": _extract_score_fallback(raw, "diversity"),
            "uniqueness": _extract_score_fallback(raw, "uniqueness"),
            "click_follow": _extract_score_fallback(raw, "click_follow"),
            "prominence": _extract_score_fallback(raw, "prominence"),
            "content_volume": _extract_score_fallback(raw, "content_volume"),
            "rationale": "",
        }


def judge_answer(
    client: GPTMessagesClient,
    config: SimulatorConfig,
    item: ContestItem,
    answer_text: str,
) -> JudgeScore:
    raw = client.call(
        model=config.judge_model,
        system=JUDGE_SYSTEM_PROMPT,
        user=_build_judge_user(item, answer_text),
        max_tokens=config.judge_max_tokens,
    )
    data = _parse_judge_payload(raw)
    return JudgeScore(
        relevance=clamp_score(data.get("relevance", 0)),
        fluency=clamp_score(data.get("fluency", 0)),
        diversity=clamp_score(data.get("diversity", 0)),
        uniqueness=clamp_score(data.get("uniqueness", 0)),
        click_follow=clamp_score(data.get("click_follow", 0)),
        prominence=clamp_score(data.get("prominence", 0)),
        content_volume=clamp_score(data.get("content_volume", 0)),
        rationale=str(data.get("rationale", "")).strip(),
    )
