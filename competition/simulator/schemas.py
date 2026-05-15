from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class SourceDocument:
    source_id: int
    label: str
    title: str
    content: str
    url: str
    search_rank: int


@dataclass(frozen=True)
class ProvidedVisibilityScore:
    word_volu: float
    posi_prom: float
    word_posi: float
    rele: float
    infl: float
    div: float
    uniq: float
    clic: float
    subj_posi: float
    subj_volu: float
    aver_subj: float
    final_score: float


@dataclass(frozen=True)
class ContestItem:
    item_id: str
    query: str
    texts: list[SourceDocument]
    target_index: int
    generated_original_answer: str | None = None
    visibility_before: ProvidedVisibilityScore | None = None

    @property
    def target(self) -> SourceDocument:
        return self.texts[self.target_index]

    def with_target_content(self, target_content: str, *, target_label: str) -> ContestItem:
        texts = list(self.texts)
        texts[self.target_index] = replace(self.target, content=target_content, label=target_label)
        return replace(self, texts=texts)


@dataclass(frozen=True)
class AnswerResult:
    answer_text: str
    prompt_docs_order: list[int]


@dataclass(frozen=True)
class ObjectiveScore:
    weighted_visibility: float
    coverage_ratio: float
    position_prominence: float
    target_chars: float
    total_chars: float
    total_cited_chars: float
    target_weighted_chars: float
    total_weighted_chars: float
    total_cited_weighted_chars: float
    target_position_weight: float
    total_position_weight: float
    total_cited_position_weight: float
    target_sentence_hits: int
    total_sentences: int

    @property
    def word_volu(self) -> float:
        return self.coverage_ratio

    @property
    def posi_prom(self) -> float:
        return self.position_prominence

    @property
    def word_posi(self) -> float:
        return self.weighted_visibility

    def to_dict(self, *, include_aliases: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if include_aliases:
            payload.update(
                {
                    "word_volu": self.word_volu,
                    "posi_prom": self.posi_prom,
                    "word_posi": self.word_posi,
                }
            )
        return payload


@dataclass(frozen=True)
class JudgeScore:
    relevance: float
    fluency: float
    diversity: float
    uniqueness: float
    click_follow: float
    prominence: float
    content_volume: float
    rationale: str = ""

    @property
    def total(self) -> float:
        return (
            self.relevance
            + self.fluency
            + self.diversity
            + self.uniqueness
            + self.click_follow
            + self.prominence
            + self.content_volume
        ) / 7.0

    def to_dict(self, *, include_aliases: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if include_aliases:
            payload.update(
                {
                    "rele": self.relevance,
                    "infl": self.fluency,
                    "div": self.diversity,
                    "uniq": self.uniqueness,
                    "clic": self.click_follow,
                    "subj_posi": self.prominence,
                    "subj_volu": self.content_volume,
                    "aver_subj": self.total,
                }
            )
        return payload


@dataclass(frozen=True)
class EvaluationSnapshot:
    item_id: str
    source_label: str
    target_source_id: int
    answer: str
    objective: ObjectiveScore
    judge: JudgeScore

    @property
    def total(self) -> float:
        return 0.5 * self.objective.weighted_visibility + 0.5 * self.judge.total

    def visibility_dict(self) -> dict[str, Any]:
        return {
            "word_volu": self.objective.word_volu,
            "posi_prom": self.objective.posi_prom,
            "word_posi": self.objective.word_posi,
            "rele": self.judge.relevance,
            "infl": self.judge.fluency,
            "div": self.judge.diversity,
            "uniq": self.judge.uniqueness,
            "clic": self.judge.click_follow,
            "subj_posi": self.judge.prominence,
            "subj_volu": self.judge.content_volume,
            "aver_subj": self.judge.total,
            "final_score": self.total,
        }


@dataclass(frozen=True)
class BeforeScoreSmokeCheck:
    official_word_volu: float
    simulator_word_volu: float
    word_volu_gap: float
    official_posi_prom: float
    simulator_posi_prom: float
    posi_prom_gap: float
    official_word_posi: float
    simulator_word_posi: float
    word_posi_gap: float
    official_ai: float
    simulator_ai: float
    ai_gap: float
    official_total: float
    simulator_total: float
    total_gap: float


@dataclass(frozen=True)
class EvaluationResult:
    before: EvaluationSnapshot
    after: EvaluationSnapshot
    provided_before_visibility: ProvidedVisibilityScore | None = None
    before_smoke_check: BeforeScoreSmokeCheck | None = None

    @property
    def delta(self) -> float:
        return self.after.total - self.before.total

    @property
    def objective_delta(self) -> float:
        return self.after.objective.weighted_visibility - self.before.objective.weighted_visibility

    @property
    def ai_delta(self) -> float:
        return self.after.judge.total - self.before.judge.total

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AggregateReport:
    count: int
    avg_before_total: float
    avg_after_total: float
    avg_delta: float
    avg_objective_delta: float
    avg_ai_delta: float
    win_rate: float
    item_results: list[dict[str, Any]] = field(default_factory=list)
