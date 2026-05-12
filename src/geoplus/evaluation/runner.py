import random
import sys

from geoplus.anthropic_client import call_model
from geoplus.paths import dataset_file, main_prompt_path

MAX_CHARS = 50000


def _label(name: str, style: str) -> str:
    if style == "fullwidth":
        return f"【{name}】"
    return f"[{name}]"


def _build_user_message(question_text: str, docs_text: str, style: str, source_name: str) -> str:
    section_question = _label("预设问题", style)
    section_docs = _label("提供的文档", style)
    example = _label(source_name, "square")
    return (
        "请基于以下所有文档回答问题。\n\n"
        + section_question
        + "\n"
        + question_text
        + "\n\n"
        + section_docs
        + "\n"
        + docs_text
        + "\n\n请根据评审规则，基于以上所有文档生成回答，并在回答中使用[文件名]格式标注引用来源（例如[1.md]、[before.md]、"
        + example
        + "等）。"
    )


def call_llm(messages: list[dict]) -> str:
    try:
        return call_model(messages, max_tokens=32768, timeout=300)
    except Exception as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return ""


def run_evaluation(
    *,
    dataset_id: int,
    source_name: str,
    output_name: str,
    style: str,
    start_message: str,
    missing_message: str | None = None,
    competitor_names: tuple[str, ...] = ("1.md", "2.md", "3.md", "4.md"),
) -> None:
    source_path = dataset_file(dataset_id, source_name)
    if not source_path.exists():
        if missing_message:
            print(missing_message.format(path=source_path, dataset=dataset_id))
            raise SystemExit(1)
        raise FileNotFoundError(source_path)

    source_text = source_path.read_text(encoding="utf-8")
    question_text = dataset_file(dataset_id, "question.md").read_text(encoding="utf-8")
    main_prompt = main_prompt_path().read_text(encoding="utf-8")

    other_texts = []
    for name in competitor_names:
        file_path = dataset_file(dataset_id, name)
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        if content.strip():
            other_texts.append(_label(file_path.name, style) + "\n" + content)

    all_docs = other_texts + [_label(source_name, style) + "\n" + source_text]
    random.shuffle(all_docs)
    docs_concat = "\n\n".join(all_docs)
    docs_truncated = docs_concat[:MAX_CHARS] if len(docs_concat) > MAX_CHARS else docs_concat
    user_msg = _build_user_message(question_text, docs_truncated, style, source_name)

    print(start_message)
    result = call_llm([
        {"role": "system", "content": main_prompt},
        {"role": "user", "content": user_msg},
    ])

    out_path = dataset_file(dataset_id, output_name)
    out_path.write_text(result, encoding="utf-8")
    print(f"Saved: {out_path}")
