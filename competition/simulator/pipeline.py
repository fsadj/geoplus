from __future__ import annotations

from pathlib import Path

from .answer import generate_answer
from .client import GPTMessagesClient
from .config import SimulatorConfig, load_config
from .data import load_json_item, load_markdown_item, resolve_after_path
from .judge import judge_answer
from .objective import DEFAULT_OBJECTIVE_PROFILE, ObjectiveProfile, score_objective
from .reporting import aggregate_results
from .schemas import BeforeScoreSmokeCheck, ContestItem, EvaluationResult, EvaluationSnapshot, ProvidedVisibilityScore


def _evaluate_single_state(
    client: GPTMessagesClient,
    config: SimulatorConfig,
    item: ContestItem,
    source_label: str,
    *,
    answer_override: str | None = None,
    objective_profile: ObjectiveProfile | None = None,
) -> EvaluationSnapshot:
    if answer_override is None:
        answer_text = generate_answer(client, config, item).answer_text
    else:
        answer_text = answer_override
    objective = score_objective(
        answer_text,
        target_source_id=item.target.source_id,
        profile=objective_profile or DEFAULT_OBJECTIVE_PROFILE,
    )
    judge = judge_answer(client, config, item, answer_text)
    return EvaluationSnapshot(
        item_id=item.item_id,
        source_label=source_label,
        target_source_id=item.target.source_id,
        answer=answer_text,
        objective=objective,
        judge=judge,
    )


def _build_smoke_check(before_snapshot: EvaluationSnapshot, official_score: ProvidedVisibilityScore | None) -> BeforeScoreSmokeCheck | None:
    if official_score is None:
        return None
    return BeforeScoreSmokeCheck(
        official_word_volu=official_score.word_volu,
        simulator_word_volu=before_snapshot.objective.coverage_ratio,
        word_volu_gap=before_snapshot.objective.coverage_ratio - official_score.word_volu,
        official_posi_prom=official_score.posi_prom,
        simulator_posi_prom=before_snapshot.objective.position_prominence,
        posi_prom_gap=before_snapshot.objective.position_prominence - official_score.posi_prom,
        official_word_posi=official_score.word_posi,
        simulator_word_posi=before_snapshot.objective.weighted_visibility,
        word_posi_gap=before_snapshot.objective.weighted_visibility - official_score.word_posi,
        official_ai=official_score.aver_subj,
        simulator_ai=before_snapshot.judge.total,
        ai_gap=before_snapshot.judge.total - official_score.aver_subj,
        official_total=official_score.final_score,
        simulator_total=before_snapshot.total,
        total_gap=before_snapshot.total - official_score.final_score,
    )


def _evaluate_item_before_after(
    client: GPTMessagesClient,
    config: SimulatorConfig,
    item: ContestItem,
    *,
    before_label: str,
    after_text: str | None,
    after_label: str,
    objective_profile: ObjectiveProfile | None = None,
) -> EvaluationResult:
    before_answer = item.generated_original_answer
    before_snapshot = _evaluate_single_state(
        client,
        config,
        item,
        before_label,
        answer_override=before_answer,
        objective_profile=objective_profile,
    )
    after_item = item.with_target_content(after_text, target_label=after_label) if after_text is not None else item
    after_snapshot = _evaluate_single_state(
        client,
        config,
        after_item,
        after_label,
        objective_profile=objective_profile,
    )
    return EvaluationResult(
        before=before_snapshot,
        after=after_snapshot,
        provided_before_visibility=item.visibility_before,
        before_smoke_check=_build_smoke_check(before_snapshot, item.visibility_before),
    )


def evaluate_item_before_after(
    item: ContestItem,
    *,
    after_text: str | None = None,
    after_label: str = "after.txt",
    config: SimulatorConfig | None = None,
    objective_profile: ObjectiveProfile | None = None,
) -> EvaluationResult:
    config = config or load_config()
    client = GPTMessagesClient(config)
    before_label = "provided_original_answer" if item.generated_original_answer else item.target.label
    effective_after_label = after_label if after_text is not None else item.target.label
    return _evaluate_item_before_after(
        client,
        config,
        item,
        before_label=before_label,
        after_text=after_text,
        after_label=effective_after_label,
        objective_profile=objective_profile,
    )


def evaluate_before_after(
    dataset_id: int,
    *,
    after_name: str | None = None,
    after_path: str | None = None,
    config: SimulatorConfig | None = None,
    objective_profile: ObjectiveProfile | None = None,
) -> EvaluationResult:
    config = config or load_config()
    client = GPTMessagesClient(config)
    before_item = load_markdown_item(dataset_id)
    resolved_after_path = resolve_after_path(dataset_id, after_name=after_name, after_path=after_path)
    after_text = resolved_after_path.read_text(encoding="utf-8").strip() if resolved_after_path else None
    after_label = resolved_after_path.name if resolved_after_path else before_item.target.label
    return _evaluate_item_before_after(
        client,
        config,
        before_item,
        before_label="before.md",
        after_text=after_text,
        after_label=after_label,
        objective_profile=objective_profile,
    )


def evaluate_many(
    dataset_ids: list[int],
    *,
    after_name: str | None = None,
    after_path: str | None = None,
    config: SimulatorConfig | None = None,
    objective_profile: ObjectiveProfile | None = None,
):
    config = config or load_config()
    client = GPTMessagesClient(config)
    results = []
    for dataset_id in dataset_ids:
        item = load_markdown_item(dataset_id)
        resolved_after_path = resolve_after_path(dataset_id, after_name=after_name, after_path=after_path)
        after_text = resolved_after_path.read_text(encoding="utf-8").strip() if resolved_after_path else None
        after_label = resolved_after_path.name if resolved_after_path else item.target.label
        results.append(
            _evaluate_item_before_after(
                client,
                config,
                item,
                before_label="before.md",
                after_text=after_text,
                after_label=after_label,
                objective_profile=objective_profile,
            )
        )
    return aggregate_results(results)


def evaluate_json_many(
    item_paths: list[Path],
    *,
    after_paths: list[Path] | None = None,
    input_mode: str = "strict",
    config: SimulatorConfig | None = None,
    objective_profile: ObjectiveProfile | None = None,
):
    if after_paths is not None and len(after_paths) != len(item_paths):
        raise ValueError("after_paths length must match item_paths length")
    config = config or load_config()
    client = GPTMessagesClient(config)
    results = []
    for index, item_path in enumerate(item_paths):
        item = load_json_item(item_path, input_mode=input_mode)
        current_after_path = after_paths[index] if after_paths is not None else None
        after_text = current_after_path.read_text(encoding="utf-8").strip() if current_after_path else None
        after_label = current_after_path.name if current_after_path else item.target.label
        before_label = "provided_original_answer" if item.generated_original_answer else item.target.label
        results.append(
            _evaluate_item_before_after(
                client,
                config,
                item,
                before_label=before_label,
                after_text=after_text,
                after_label=after_label,
                objective_profile=objective_profile,
            )
        )
    return aggregate_results(results)
