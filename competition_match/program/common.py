from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPETITION_ROOT = REPO_ROOT / "competition"
SRC_ROOT = COMPETITION_ROOT / "src"

for path in (str(COMPETITION_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

DATA_ROOT = REPO_ROOT / "competition_match" / "data"
OUTPUT_ROOT = REPO_ROOT / "competition_match" / "outputs"

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]{2,8}")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*$")
CITATION_RE = re.compile(r"\[(\d+)\]")
SENTENCE_RE = re.compile(r"(?<=[。！？!?])|\n+")

STOPWORDS = {
    "一个",
    "一些",
    "以及",
    "为了",
    "可以",
    "需要",
    "问题",
    "核心",
    "文章",
    "内容",
    "本文",
    "我们",
    "你们",
    "他们",
    "这个",
    "那个",
    "这些",
    "那些",
    "进行",
    "基于",
    "关于",
    "相关",
    "结果",
    "分析",
    "说明",
    "情况",
    "方法",
    "部分",
    "标题",
    "文本",
    "数据",
    "方案",
    "优化",
}


def dataset_dir(dataset_id: int) -> Path:
    return DATA_ROOT / str(dataset_id)


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_docs(dataset_id: int) -> list[dict[str, object]]:
    base = dataset_dir(dataset_id)
    docs: list[dict[str, object]] = []
    for index in range(1, 6):
        path = base / f"{index}.md"
        docs.append(
            {
                "index": index,
                "path": path,
                "name": path.name,
                "content": read_text(path),
            }
        )
    return docs


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text) if len(token) >= 2 and token not in STOPWORDS]


def extract_keywords(texts: Iterable[str], limit: int = 12) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        for token in tokenize(text):
            counter[token] += 1
    return [token for token, _ in counter.most_common(limit)]


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def infer_question_from_docs(docs: list[dict[str, object]]) -> str:
    headings: list[str] = []
    for doc in docs:
        headings.extend(extract_headings(str(doc["content"])))
    if headings:
        counts = Counter(headings)
        topic = counts.most_common(1)[0][0]
        return topic if topic.endswith(("?", "？")) else f"{topic}是什么？"

    keywords = extract_keywords((str(doc["content"]) for doc in docs), limit=6)
    if len(keywords) >= 2:
        return f"{keywords[0]}和{keywords[1]}的核心问题是什么？"
    if keywords:
        return f"{keywords[0]}是什么？"
    return "这组文章讨论的核心问题是什么？"


def ensure_question(dataset_id: int) -> tuple[str, Path, bool]:
    base = dataset_dir(dataset_id)
    path = base / "question.md"
    existing = read_optional_text(path)
    if existing:
        return existing, path, False
    docs = load_docs(dataset_id)
    question = infer_question_from_docs(docs)
    write_text(path, question)
    return question, path, True


def load_baseline_answer(dataset_id: int) -> tuple[str, Path]:
    base = dataset_dir(dataset_id)
    path = base / "test_before.md"
    return read_text(path), path


def doc_blocks(docs: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for doc in docs:
        index = int(doc["index"])
        content = str(doc["content"])
        path = doc["path"]
        blocks.append(
            f"[文档{index}]\n"
            f"文件: {path.name}\n"
            f"内容:\n{content}"
        )
    return "\n\n".join(blocks)


def source_summary(docs: list[dict[str, object]]) -> str:
    keywords = extract_keywords((str(doc["content"]) for doc in docs), limit=10)
    if not keywords:
        return ""
    return "、".join(keywords)


def build_heuristic_article(
    question: str,
    target_doc: dict[str, object],
    other_docs: list[dict[str, object]],
    baseline_answer: str,
) -> str:
    target_content = str(target_doc["content"])
    target_headings = extract_headings(target_content)
    title = target_headings[0] if target_headings else question.rstrip("？?")
    if not title:
        title = f"第{target_doc['index']}篇文章优化稿"

    target_sentences = split_sentences(target_content)
    baseline_sentences = split_sentences(baseline_answer)
    shared_keywords = extract_keywords((str(doc["content"]) for doc in [target_doc, *other_docs]), limit=8)
    shared_line = "、".join(shared_keywords[:5]) if shared_keywords else ""

    lead = target_sentences[0] if target_sentences else target_content[:140]
    support = target_sentences[1:4] if len(target_sentences) > 1 else []
    baseline_hint = baseline_sentences[0] if baseline_sentences else ""

    lines = [f"# {title}", "", "## 核心表述", lead]
    if baseline_hint:
        lines.extend(["", "## 初始引用线索", baseline_hint])
    if shared_line:
        lines.extend(["", "## 共同信息", f"本文围绕 {shared_line} 展开，并尽量把与其他文章一致的关键点写得更清楚。"])
    if support:
        lines.extend(["", "## 细化补充"])
        for sentence in support:
            lines.append(f"- {sentence}")
    lines.extend([
        "",
        "## 结论",
        f"{question.rstrip('？?')}相关的核心内容在本文中已经尽量前置，便于后续生成答案时优先引用。",
    ])
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def timestamp() -> str:
    return datetime.now(UTC).isoformat()
