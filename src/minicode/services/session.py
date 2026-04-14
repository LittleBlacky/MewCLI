"""Session management service."""
import json
from pathlib import Path
from typing import Optional


class SessionManager:
    """Manage user sessions."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".mini-agent-cli" / "sessions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, session_id: str) -> dict:
        """Create a new session."""
        session = {
            "id": session_id,
            "messages": [],
            "created": str(Path.cwd()),
            "checkpoint": None,
        }
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID."""
        fp = self.storage_dir / f"{session_id}.json"
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
        return None

    def _save_session(self, session: dict) -> None:
        fp = self.storage_dir / f"{session['id']}.json"
        fp.write_text(json.dumps(session, indent=2), encoding="utf-8")

    def list_sessions(self) -> list[dict]:
        """List all sessions."""
        sessions = []
        for fp in self.storage_dir.glob("*.json"):
            try:
                sessions.append(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sessions


# Global instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(storage_dir: Optional[Path] = None) -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(storage_dir)
    return _session_manager
