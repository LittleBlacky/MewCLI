"""Checkpoint storage backend."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .checkpoint import Checkpoint


class CheckpointStore:
    """Checkpoint storage backend."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, thread_id: str, checkpoint: Checkpoint) -> None:
        thread_dir = self.storage_dir / thread_id
        thread_dir.mkdir(exist_ok=True)
        file_path = thread_dir / f"{checkpoint.checkpoint_id}.json"
        file_path.write_text(json.dumps(checkpoint.to_dict(), ensure_ascii=False))

    def load(self, thread_id: str, checkpoint_id: str) -> Optional[Checkpoint]:
        file_path = self.storage_dir / thread_id / f"{checkpoint_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text())
            return Checkpoint.from_dict(data)
        except Exception:
            return None

    def list_all(self, thread_id: str) -> list[Checkpoint]:
        thread_dir = self.storage_dir / thread_id
        if not thread_dir.exists():
            return []
        checkpoints = []
        for file in thread_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text())
                checkpoints.append(Checkpoint.from_dict(data))
            except Exception:
                continue
        return sorted(checkpoints, key=lambda c: c.created_at)

    def delete(self, thread_id: str, checkpoint_id: str) -> None:
        file_path = self.storage_dir / thread_id / f"{checkpoint_id}.json"
        if file_path.exists():
            file_path.unlink()