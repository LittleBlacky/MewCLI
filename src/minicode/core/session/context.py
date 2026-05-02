"""Session context and state management."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from .agent import Message, MessageRole


@dataclass
class SessionContext:
    """Session context - holds conversation state and metadata."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str = "default"  # For checkpointing
    created_at: float = field(default_factory=datetime.now().timestamp)
    last_activity_at: float = field(default_factory=datetime.now().timestamp)
    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""
    metadata: dict = field(default_factory=dict)

    # Context management
    max_messages: int = 50  # Max messages before warning
    max_tokens: int = 150000  # Max tokens (Claude 200K)
    compact_threshold: float = 0.7  # 70% capacity triggers compact

    # Memory injection
    preference_injected: bool = False
    knowledge_injected: bool = False
    skills_injected: bool = False

    def add_message(self, message: Message) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.last_activity_at = datetime.now().timestamp()

    def get_messages_for_llm(self) -> list[Message]:
        """Get messages in format suitable for LLM."""
        return self.messages

    def estimate_tokens(self) -> int:
        """Estimate current token count."""
        total = 0
        for msg in self.messages:
            # Rough estimation: Chinese ~2 chars/token, English ~4 chars/token
            content = msg.content if isinstance(msg, Message) else str(msg)
            total += len(content) // 2
        # Add system prompt
        total += len(self.system_prompt) // 2
        return total

    def get_token_ratio(self) -> float:
        """Get current token usage as ratio of max."""
        return self.estimate_tokens() / self.max_tokens

    def should_warn(self) -> bool:
        """Check if should warn about capacity."""
        return self.get_token_ratio() > self.compact_threshold

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "messages": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.messages],
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
            "compact_threshold": self.compact_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionContext:
        """Deserialize from dictionary."""
        messages = []
        for m in data.get("messages", []):
            if isinstance(m, dict):
                messages.append(Message.from_dict(m))
            else:
                messages.append(m)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            thread_id=data.get("thread_id", "default"),
            created_at=data.get("created_at", datetime.now().timestamp()),
            last_activity_at=data.get("last_activity_at", datetime.now().timestamp()),
            messages=messages,
            system_prompt=data.get("system_prompt", ""),
            metadata=data.get("metadata", {}),
            max_messages=data.get("max_messages", 50),
            max_tokens=data.get("max_tokens", 150000),
            compact_threshold=data.get("compact_threshold", 0.7),
        )


@dataclass
class SessionMetrics:
    """Session usage metrics."""

    total_turns: int = 0  # Total conversation turns
    total_tasks: int = 0  # Total tasks created
    tasks_completed: int = 0  # Tasks completed
    tasks_failed: int = 0  # Tasks failed
    tools_called: int = 0  # Total tool invocations
    compact_count: int = 0  # Context compaction count
    output_saved_count: int = 0  # Long outputs saved to file
    session_start: float = field(default_factory=datetime.now().timestamp)

    def increment_turn(self) -> None:
        self.total_turns += 1

    def increment_task(self) -> None:
        self.total_tasks += 1

    def get_summary(self) -> dict:
        """Get metrics summary."""
        return {
            "total_turns": self.total_turns,
            "total_tasks": self.total_tasks,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tools_called": self.tools_called,
            "compact_count": self.compact_count,
            "output_saved": self.output_saved_count,
            "session_duration": int(datetime.now().timestamp() - self.session_start),
        }


@dataclass
class SessionConfig:
    """Session configuration."""

    compact_threshold: int = 50  # Message count threshold
    compact_keep_recent: int = 5  # Keep recent N messages
    memory_on_task_complete: bool = True  # Auto-save task memory
    reflect_on_idle: bool = True  # Enable idle reflection
    reflect_interval: int = 10  # Turns between reflections
    context_limit: int = 50000  # Character limit
    max_output_chars: int = 15000  # Long output threshold
    compact_ratio: float = 0.7  # Capacity threshold for compact