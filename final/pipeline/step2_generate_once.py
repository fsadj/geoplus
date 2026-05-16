from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from final.adapters.datasets import load_baseline_answer, load_docs, load_question_lines, workspace_dir
from final.adapters.routes import list_routes
from final.adapters.search import load_reference_pool
from final.common import assert_no_reference_markers, call_with_retry, load_gpt_client, sanitize_output, write_text
from final.prompts import STEP2_SYSTEM_PROMPT, build_step2_user_prompt


def _generate_one_route(route, docs, baseline_answer, question_lines, reference_docs, config, client, output_dir):
    target_doc = docs[route.source_index - 1]
    other_docs = [doc for doc in docs if int(doc["index"]) != route.source_index]
    draft = call_with_retry(
        client,
        model=config.answer_model,
        system=STEP2_SYSTEM_PROMPT,
        user=build_step2_user_prompt(route, target_doc, other_docs, baseline_answer, question_lines, reference_docs),
        max_tokens=config.answer_max_tokens,
    )
    draft = sanitize_output(draft)
    assert_no_reference_markers(draft)
    path = output_dir / f"{route.name}.md"
    write_text(path, draft)
    return route.name, str(path)


def run(dataset_id: int) -> dict:
    docs = load_docs(dataset_id)
    question_lines = load_question_lines(dataset_id)
    baseline_answer = load_baseline_answer(dataset_id)
    reference_payload = load_reference_pool(dataset_id)
    reference_docs = reference_payload.get("available_docs", [])
    config, client = load_gpt_client()
    output_dir = workspace_dir(dataset_id) / "step2"
    output_dir.mkdir(parents=True, exist_ok=True)

    routes = list_routes()
    outputs: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(len(routes), 3)) as pool:
        futures = {
            pool.submit(_generate_one_route, route, docs, baseline_answer, question_lines, reference_docs, config, client, output_dir): route
            for route in routes
        }
        for future in as_completed(futures):
            name, path = future.result()
            outputs[name] = path
    return outputs
