"""Session manager - manages user session lifecycle."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable

from .context import SessionContext, SessionConfig, SessionMetrics


class SessionManager:
    """Manages user session lifecycle.

    Responsibilities:
    - Create/destroy sessions
    - Manage session context
    - Track session metrics
    - Handle session persistence
    """

    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.config = config or SessionConfig()
        self.storage_dir = storage_dir or Path.home() / ".minicode" / "sessions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._sessions: dict[str, SessionContext] = {}
        self._current_session: Optional[SessionContext] = None

    def create_session(
        self,
        thread_id: str = "default",
        system_prompt: str = "",
        metadata: Optional[dict] = None,
    ) -> SessionContext:
        """Create a new session."""
        session = SessionContext(
            thread_id=thread_id,
            system_prompt=system_prompt,
            metadata=metadata or {},
        )
        self._sessions[session.id] = session
        self._current_session = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_current_session(self) -> Optional[SessionContext]:
        """Get current active session."""
        return self._current_session

    def set_current_session(self, session_id: str) -> bool:
        """Set current session by ID."""
        session = self._sessions.get(session_id)
        if session:
            self._current_session = session
            return True
        return False

    def end_session(self, session_id: str, save: bool = True) -> None:
        """End a session and optionally save to disk."""
        session = self._sessions.get(session_id)
        if session and save:
            self._save_session(session)
        if self._current_session and self._current_session.id == session_id:
            self._current_session = None

    def _save_session(self, session: SessionContext) -> None:
        """Save session to disk."""
        filepath = self.storage_dir / f"session_{session.id}.json"
        data = session.to_dict()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load_session(self, session_id: str) -> Optional[SessionContext]:
        """Load session from disk."""
        filepath = self.storage_dir / f"session_{session_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            session = SessionContext.from_dict(data)
            self._sessions[session_id] = session
            return session
        return None

    def list_sessions(self) -> list[dict]:
        """List all sessions."""
        return [
            {
                "id": s.id,
                "thread_id": s.thread_id,
                "created_at": s.created_at,
                "last_activity": s.last_activity_at,
                "message_count": len(s.messages),
            }
            for s in self._sessions.values()
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            filepath = self.storage_dir / f"session_{session_id}.json"
            if filepath.exists():
                filepath.unlink()
            return True
        return False

    def get_or_create_current(
        self,
        thread_id: str = "default",
        system_prompt: str = "",
    ) -> SessionContext:
        """Get current session or create one."""
        if self._current_session:
            return self._current_session
        return self.create_session(thread_id, system_prompt)