from __future__ import annotations

from final.adapters.datasets import list_dataset_ids, prepare_dataset


def run(dataset_ids: list[int] | None = None, *, force: bool = False) -> list[str]:
    ids = dataset_ids or list_dataset_ids()
    return [str(prepare_dataset(dataset_id, force=force)) for dataset_id in ids]
