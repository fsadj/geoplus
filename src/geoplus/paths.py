from pathlib import Path

INPUT_DOC_NAMES = {"before.md", "question.md", "1.md", "2.md", "3.md", "4.md"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def src_dir() -> Path:
    return project_root() / "src"


def baseline_root() -> Path:
    return project_root() / "data" / "baseline"


def outputs_root() -> Path:
    return project_root() / "outputs"


def baseline_input_dir(dataset_id: int) -> Path:
    return baseline_root() / str(dataset_id)


def dataset_output_dir(dataset_id: int) -> Path:
    path = outputs_root() / "datasets" / str(dataset_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def charts_dir() -> Path:
    path = outputs_root() / "charts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_dir() -> Path:
    path = outputs_root() / "pdf"
    path.mkdir(parents=True, exist_ok=True)
    return path


def prompts_dir() -> Path:
    return project_root() / "prompts"


def docs_dir() -> Path:
    return project_root() / "docs"


def main_prompt_path() -> Path:
    return prompts_dir() / "main_prompt.md"


def dataset_file(dataset_id: int, file_name: str) -> Path:
    if file_name in INPUT_DOC_NAMES:
        return baseline_input_dir(dataset_id) / file_name
    return dataset_output_dir(dataset_id) / file_name


def iter_dataset_markdown_files(dataset_id: int) -> list[Path]:
    input_files = sorted(baseline_input_dir(dataset_id).glob("*.md"))
    output_files = sorted(dataset_output_dir(dataset_id).glob("*.md"))
    return input_files + output_files
