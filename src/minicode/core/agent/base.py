"""Core types and abstractions for MiniCode.

Defines the fundamental concepts: Agent, Task, Message, etc.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class AgentRole(Enum):
    """Agent role in the system."""

    LEAD = "lead"  # Lead Agent - understands tasks, decomposes, aggregates
    WORKER = "worker"  # Worker Agent - executes subtasks


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"  # Task created, not started
    RUNNING = "running"  # Task in execution
    DONE = "done"  # Task completed successfully
    FAILED = "failed"  # Task failed
    CANCELLED = "cancelled"  # Task cancelled


class MessageRole(Enum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# ============================================================================
# Core Data Classes
# ============================================================================


@dataclass
class AgentConfig:
    """Configuration for an Agent instance."""

    name: str  # Agent identifier
    role: AgentRole  # LEAD or WORKER
    tools: list[str] = field(default_factory=list)  # Available tool names
    capabilities: list[str] = field(default_factory=list)  # Special capabilities
    model: str = "claude-sonnet-4-7"  # Model to use
    temperature: float = 0.0  # LLM temperature
    max_tokens: int = 8000  # Max output tokens

    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = AgentRole(self.role)


@dataclass
class Task:
    """Task representation - a unit of work for an Agent."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""  # Human-readable task description
    assigned_to: Optional[str] = None  # Agent name that owns this task
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None  # Execution result
    error: Optional[str] = None  # Error message if failed
    parent_id: Optional[str] = None  # Parent task ID (for decomposed tasks)
    children_ids: list[str] = field(default_factory=list)  # Child task IDs
    created_at: float = field(default_factory=datetime.now().timestamp)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)  # Additional task metadata

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)

    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now().timestamp()

    def complete(self, result: str) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.DONE
        self.result = result
        self.completed_at = datetime.now().timestamp()

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now().timestamp()

    def cancel(self) -> None:
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now().timestamp()

    @property
    def duration(self) -> Optional[float]:
        """Get task execution duration in seconds."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Create Task from dictionary."""
        return cls(**data)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0  # Execution duration in seconds
    tools_used: list[str] = field(default_factory=list)  # Tools invoked
    metadata: dict = field(default_factory=dict)


@dataclass
class Message:
    """Message in a conversation."""

    role: MessageRole
    content: str
    tool_calls: Optional[list[dict]] = None  # For assistant messages
    tool_call_id: Optional[str] = None  # For tool messages
    name: Optional[str] = None  # Tool name for tool messages
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=datetime.now().timestamp)

    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = MessageRole(self.role)

    def to_langchain(self) -> Any:
        """Convert to LangChain message format."""
        from langchain_core.messages import (
            HumanMessage,
            AIMessage,
            SystemMessage,
            ToolMessage,
        )

        if self.role == MessageRole.USER:
            return HumanMessage(content=self.content)
        elif self.role == MessageRole.ASSISTANT:
            return AIMessage(
                content=self.content,
                tool_calls=self.tool_calls,
            )
        elif self.role == MessageRole.SYSTEM:
            return SystemMessage(content=self.content)
        elif self.role == MessageRole.TOOL:
            return ToolMessage(
                content=self.content,
                tool_call_id=self.tool_call_id or "",
                name=self.name or "",
            )
        return HumanMessage(content=self.content)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """Create Message from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().timestamp()),
        )


# ============================================================================
# Lead Agent Specific Types
# ============================================================================


@dataclass
class DecompositionResult:
    """Result of task decomposition by Lead Agent."""

    original_task: str  # Original task description
    subtasks: list[Task]  # Decomposed subtasks
    reasoning: str  # Why these subtasks were chosen
    estimated_duration: float  # Estimated total duration in seconds


# ============================================================================
# Team Collaboration Types
# ============================================================================


@dataclass
class TeamEvent:
    """Event in team collaboration."""

    type: str  # Event type: task_assigned, task_completed, worker_started, etc.
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=datetime.now().timestamp)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }