from __future__ import annotations

import random

from .client import GPTMessagesClient
from .config import SimulatorConfig
from .schemas import AnswerResult, ContestItem


ANSWER_SYSTEM_PROMPT = """你是比赛模拟系统中的生成式搜索引擎。\n你的任务是基于给定问题和 5 篇候选文本，生成一份综合答案。\n要求：\n1. 只使用提供文本中的信息，不要引入文本外新事实。\n2. 以自然、权威、结构清晰的中文回答。\n3. 任何来自某篇文本的判断、事实、解释或措辞后，都要用方括号标注来源序号，例如 [1]、[3]。\n4. 同一句可以引用多个来源，例如 [1][4]。\n5. 可以参考标题、URL 和传统搜索位次理解文本定位，但答案事实仍然只能来自文本内容本身。\n6. 不要解释评分规则，不要输出元注释。\n7. 默认按读者最关心的主问题先给结论，再展开。"""


def _docs_block(item: ContestItem, *, seed: int | None = None) -> tuple[str, list[int]]:
    docs = list(item.texts)
    rng = random.Random(seed)
    rng.shuffle(docs)
    parts = []
    order = []
    for doc in docs:
        order.append(doc.source_id)
        parts.append(
            f"[文档{doc.source_id}]\n"
            f"传统搜索位次: {doc.search_rank}\n"
            f"URL: {doc.url}\n"
            f"标题: {doc.title}\n"
            f"内容:\n{doc.content}"
        )
    return "\n\n".join(parts), order


def generate_answer(
    client: GPTMessagesClient,
    config: SimulatorConfig,
    item: ContestItem,
    *,
    seed: int | None = None,
) -> AnswerResult:
    docs_block, order = _docs_block(item, seed=seed)
    user = (
        f"【用户问题】\n{item.query}\n\n"
        f"【候选文本】\n{docs_block}\n\n"
        "请输出一份最终答案。答案中的每个关键判断句尽量标注来源序号。"
    )
    answer_text = client.call(
        model=config.answer_model,
        system=ANSWER_SYSTEM_PROMPT,
        user=user,
        max_tokens=config.answer_max_tokens,
    )
    return AnswerResult(answer_text=answer_text, prompt_docs_order=order)
