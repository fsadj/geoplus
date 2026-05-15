from __future__ import annotations

from dataclasses import asdict

from .schemas import AggregateReport, EvaluationResult


def aggregate_results(results: list[EvaluationResult]) -> AggregateReport:
    if not results:
        return AggregateReport(
            count=0,
            avg_before_total=0.0,
            avg_after_total=0.0,
            avg_delta=0.0,
            avg_objective_delta=0.0,
            avg_ai_delta=0.0,
            win_rate=0.0,
            item_results=[],
        )
    count = len(results)
    avg_before_total = sum(result.before.total for result in results) / count
    avg_after_total = sum(result.after.total for result in results) / count
    avg_delta = sum(result.delta for result in results) / count
    avg_objective_delta = sum(result.objective_delta for result in results) / count
    avg_ai_delta = sum(result.ai_delta for result in results) / count
    win_rate = sum(1 for result in results if result.delta > 0) / count * 100
    item_results = []
    for result in results:
        item_payload = {
            "item_id": result.before.item_id,
            "before_total": result.before.total,
            "after_total": result.after.total,
            "delta": result.delta,
            "objective_delta": result.objective_delta,
            "ai_delta": result.ai_delta,
            "before_answer": result.before.answer,
            "after_answer": result.after.answer,
            "before_objective": result.before.objective.to_dict(include_aliases=True),
            "after_objective": result.after.objective.to_dict(include_aliases=True),
            "before_judge": result.before.judge.to_dict(include_aliases=True),
            "after_judge": result.after.judge.to_dict(include_aliases=True),
            "before_visibility": result.before.visibility_dict(),
            "after_visibility": result.after.visibility_dict(),
        }
        if result.provided_before_visibility is not None:
            item_payload["provided_before_visibility"] = asdict(result.provided_before_visibility)
        if result.before_smoke_check is not None:
            item_payload["before_smoke_check"] = asdict(result.before_smoke_check)
        item_results.append(item_payload)
    return AggregateReport(
        count=count,
        avg_before_total=avg_before_total,
        avg_after_total=avg_after_total,
        avg_delta=avg_delta,
        avg_objective_delta=avg_objective_delta,
        avg_ai_delta=avg_ai_delta,
        win_rate=win_rate,
        item_results=item_results,
    )
