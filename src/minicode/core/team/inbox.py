"""Team collaboration types and utilities."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Awaitable


class WorkerStatus(Enum):
    """Worker Agent status."""

    IDLE = "idle"  # Waiting for task
    BUSY = "busy"  # Executing task
    STOPPED = "stopped"  # Stopped


@dataclass
class WorkerInfo:
    """Information about a worker agent."""

    id: str
    name: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_task_id: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    created_at: float = field(default_factory=datetime.now().timestamp)
    last_heartbeat: float = field(default_factory=datetime.now().timestamp)
    metadata: dict = field(default_factory=dict)

    def is_alive(self, timeout: float = 60.0) -> bool:
        """Check if worker is alive (heartbeat within timeout)."""
        return datetime.now().timestamp() - self.last_heartbeat < timeout

    def update_heartbeat(self) -> None:
        """Update worker heartbeat timestamp."""
        self.last_heartbeat = datetime.now().timestamp()


@dataclass
class InboxMessage:
    """Message in worker inbox."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: Optional[str] = None  # Sender agent ID
    to_agent: str = ""  # Recipient agent ID
    type: str = "task"  # Message type: task, result, control
    content: str = ""
    task_id: Optional[str] = None  # Associated task ID
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=datetime.now().timestamp)
    read: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "type": self.type,
            "content": self.content,
            "task_id": self.task_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "read": self.read,
        }


class Inbox:
    """Message inbox for agent communication.

    Each agent has its own inbox for receiving messages.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._messages: list[InboxMessage] = []
        self._lock = asyncio.Lock()

    async def send(
        self,
        to_agent: str,
        msg_type: str,
        content: str,
        task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> InboxMessage:
        """Send a message to an agent."""
        msg = InboxMessage(
            from_agent=self.agent_id,
            to_agent=to_agent,
            type=msg_type,
            content=content,
            task_id=task_id,
            metadata=metadata or {},
        )
        async with self._lock:
            self._messages.append(msg)
        return msg

    async def receive(self, mark_read: bool = True) -> Optional[InboxMessage]:
        """Receive next unread message."""
        async with self._lock:
            for msg in self._messages:
                if not msg.read and msg.to_agent == self.agent_id:
                    if mark_read:
                        msg.read = True
                    return msg
        return None

    async def receive_all(self, mark_read: bool = True) -> list[InboxMessage]:
        """Receive all unread messages."""
        messages = []
        async with self._lock:
            for msg in self._messages:
                if not msg.read and msg.to_agent == self.agent_id:
                    messages.append(msg)
                    if mark_read:
                        msg.read = True
        return messages

    async def clear(self) -> None:
        """Clear all messages."""
        async with self._lock:
            self._messages.clear()

    def count_unread(self) -> int:
        """Count unread messages."""
        return sum(1 for msg in self._messages if not msg.read and msg.to_agent == self.agent_id)