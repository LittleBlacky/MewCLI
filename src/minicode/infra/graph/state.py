"""Graph state definitions."""
from __future__ import annotations

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    """Combined graph state."""
    messages: Annotated[list, add_messages]
    tool_messages: list
    last_summary: str
    mode: str
    task_count: int
    permission_rules: list
    consecutive_denials: int


class GraphMessageState(TypedDict):
    """Message state for graph."""
    messages: Annotated[list, add_messages]


class GraphTaskState(TypedDict):
    """Task state for graph."""
    task_items: list[dict]
    pending_tasks: list[dict]


class GraphExecutionState(TypedDict):
    """Execution state for graph."""
    evaluation_score: float
    execution_steps: list[str]
    error_recovery_count: int


def create_initial_state(messages: Optional[list] = None, mode: str = "default") -> dict:
    """Create initial graph state."""
    return {
        "messages": messages or [],
        "tool_messages": [],
        "last_summary": "",
        "mode": mode,
        "task_count": 0,
        "permission_rules": [],
        "consecutive_denials": 0,
    }