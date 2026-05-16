from __future__ import annotations

import shutil
from pathlib import Path

from final.common import DATA_ROOT, REPO_ROOT, WORKSPACE_ROOT, DatasetMapping, load_json, parse_question_lines, read_optional_text, read_text, write_json, write_text

REPORT5_DATASETS_PATH = REPO_ROOT / "competition" / "config" / "report5_datasets.json"
COMPETITION_MATCH_DATA_ROOT = REPO_ROOT / "competition_match" / "data"


def load_dataset_mappings() -> list[DatasetMapping]:
    payload = load_json(REPORT5_DATASETS_PATH)
    if not isinstance(payload, list):
        raise ValueError(f"invalid dataset mapping file: {REPORT5_DATASETS_PATH}")
    return [DatasetMapping(**row) for row in payload]


def list_dataset_ids() -> list[int]:
    return [row.internal_dataset_id for row in load_dataset_mappings()]


def get_dataset_mapping(dataset_id: int) -> DatasetMapping:
    for row in load_dataset_mappings():
        if row.internal_dataset_id == dataset_id:
            return row
    raise KeyError(f"unknown dataset id: {dataset_id}")


def final_dataset_dir(dataset_id: int) -> Path:
    return DATA_ROOT / str(dataset_id)


def workspace_dir(dataset_id: int) -> Path:
    return WORKSPACE_ROOT / str(dataset_id)


def source_dataset_dir(dataset_id: int) -> Path:
    mapping = get_dataset_mapping(dataset_id)
    return COMPETITION_MATCH_DATA_ROOT / str(mapping.match_dataset_id)


def prepare_dataset(dataset_id: int, *, force: bool = False) -> Path:
    mapping = get_dataset_mapping(dataset_id)
    source_dir = source_dataset_dir(dataset_id)
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    target_dir = final_dataset_dir(dataset_id)
    workspace = workspace_dir(dataset_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    for index in range(1, 6):
        destination = target_dir / f"{index}.md"
        if force or not destination.exists():
            shutil.copyfile(source_dir / f"{index}.md", destination)

    question_source = source_dir / "question.md"
    question_destination = target_dir / "question.txt"
    if question_source.exists() and (force or not question_destination.exists()):
        write_text(question_destination, read_text(question_source))

    test_before_source = source_dir / "test_before.md"
    if test_before_source.exists() and (force or not (target_dir / "test_before.md").exists()):
        shutil.copyfile(test_before_source, target_dir / "test_before.md")

    manifest = {
        "dataset_id": dataset_id,
        "match_dataset_id": mapping.match_dataset_id,
        "legacy_dataset_id": mapping.legacy_dataset_id,
        "title": mapping.title,
        "source_dir": str(source_dir),
        "question_present": question_source.exists(),
    }
    write_json(target_dir / "manifest.json", manifest)
    return target_dir


def load_manifest(dataset_id: int) -> dict:
    payload = load_json(final_dataset_dir(dataset_id) / "manifest.json")
    if not isinstance(payload, dict):
        raise ValueError(f"manifest missing for dataset {dataset_id}")
    return payload


def load_docs(dataset_id: int) -> list[dict[str, object]]:
    base = final_dataset_dir(dataset_id)
    docs: list[dict[str, object]] = []
    for index in range(1, 6):
        path = base / f"{index}.md"
        docs.append({"index": index, "path": path, "name": path.name, "content": read_text(path)})
    return docs


def load_question_text(dataset_id: int) -> str | None:
    return read_optional_text(final_dataset_dir(dataset_id) / "question.txt")


def save_question_text(dataset_id: int, lines: list[str]) -> Path:
    path = final_dataset_dir(dataset_id) / "question.txt"
    write_text(path, "\n".join(lines))
    return path


def save_question_groups(dataset_id: int, groups: list[dict[str, object]]) -> Path:
    path = final_dataset_dir(dataset_id) / "question_groups.json"
    write_json(path, groups)
    return path


def load_question_groups(dataset_id: int) -> list[dict[str, object]]:
    payload = load_json(final_dataset_dir(dataset_id) / "question_groups.json")
    if not isinstance(payload, list):
        return []
    groups: list[dict[str, object]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        question = str(row.get("question", "")).strip()
        aliases = row.get("aliases", [])
        alias_lines = [str(alias).strip() for alias in aliases] if isinstance(aliases, list) else []
        if not question:
            continue
        groups.append({"question": question, "aliases": [alias for alias in alias_lines if alias]})
    return groups


def load_question_lines(dataset_id: int) -> list[str]:
    groups = load_question_groups(dataset_id)
    if groups:
        return [str(group["question"]).strip() for group in groups if str(group.get("question", "")).strip()]
    return parse_question_lines(load_question_text(dataset_id))


def load_baseline_answer(dataset_id: int) -> str:
    path = final_dataset_dir(dataset_id) / "test_before.md"
    return read_optional_text(path) or ""


def final_after_path(dataset_id: int) -> Path:
    return final_dataset_dir(dataset_id) / "after.md"
