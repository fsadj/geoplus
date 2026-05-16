from __future__ import annotations

from final.adapters.datasets import final_after_path, load_docs, load_question_lines, workspace_dir
from final.adapters.routes import get_extra_route, list_routes
from final.adapters.search import load_reference_pool
from final.common import assert_no_reference_markers, call_with_retry, load_gpt_client, read_text, sanitize_output, write_text
from final.prompts import EXTRA_COVERAGE_FLOOR_SYSTEM_PROMPT, FINALIZE_SYSTEM_PROMPT, build_extra_coverage_floor_user_prompt, build_finalize_user_prompt


def run(dataset_id: int) -> str:
    question_lines = load_question_lines(dataset_id)
    citation_dir = workspace_dir(dataset_id) / "step2_citation"
    drafts = []
    for route in list_routes():
        path = citation_dir / f"{route.name}.md"
        drafts.append({"route": route.name, "content": read_text(path)})
    config, client = load_gpt_client()
    final_text = call_with_retry(
        client,
        model=config.answer_model,
        system=FINALIZE_SYSTEM_PROMPT,
        user=build_finalize_user_prompt(question_lines, drafts),
        max_tokens=config.answer_max_tokens,
    )
    final_text = sanitize_output(final_text)
    assert_no_reference_markers(final_text)
    output_path = final_after_path(dataset_id)
    write_text(output_path, final_text)
    return str(output_path)


def run_extra(dataset_id: int) -> str:
    route = get_extra_route()
    docs = load_docs(dataset_id)
    question_lines = load_question_lines(dataset_id)
    reference_payload = load_reference_pool(dataset_id)
    reference_docs = reference_payload.get("available_docs", [])
    config, client = load_gpt_client()
    final_text = call_with_retry(
        client,
        model=config.answer_model,
        system=EXTRA_COVERAGE_FLOOR_SYSTEM_PROMPT,
        user=build_extra_coverage_floor_user_prompt(route, docs, question_lines, reference_docs),
        max_tokens=config.answer_max_tokens,
    )
    final_text = sanitize_output(final_text)
    assert_no_reference_markers(final_text)
    output_path = workspace_dir(dataset_id) / "extra" / f"{route.name}.md"
    write_text(output_path, final_text)
    return str(output_path)
