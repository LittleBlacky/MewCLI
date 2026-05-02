"""Checkpoint data structure."""
from __future__ import annotations

from typing import Optional


class Checkpoint:
    """Checkpoint data structure."""

    def __init__(
        self,
        state: dict,
        checkpoint_id: str,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.state = state
        self.checkpoint_id = checkpoint_id
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self.created_at = 0

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "checkpoint_id": self.checkpoint_id,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            state=data["state"],
            checkpoint_id=data["checkpoint_id"],
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata"),
        )