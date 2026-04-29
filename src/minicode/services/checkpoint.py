"""Checkpoint service for session persistence."""
import os
from pathlib import Path
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


class CheckpointManager:
    """Manages checkpoints for agent sessions."""

    def __init__(self, use_sqlite: bool = False, db_path: Optional[str] = None):
        self.use_sqlite = use_sqlite
        self.db_path = db_path

        if use_sqlite and db_path:
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            self.checkpointer = SqliteSaver.from_conn_string(db_path)
        else:
            self.checkpointer = MemorySaver()

    def get_session_config(self, thread_id: str):
        """Get session config with checkpointing."""
        return {"configurable": {"thread_id": thread_id}}

    def clear_session(self, thread_id: str) -> None:
        """Clear a session's checkpoint data."""
        if hasattr(self.checkpointer, 'delete'):
            config = self.get_session_config(thread_id)
            try:
                self.checkpointer.delete(config)
            except Exception:
                pass


__all__ = ["CheckpointManager"]
