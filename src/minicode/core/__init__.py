"""Core module - central abstractions for MiniCode.

This module contains the core abstractions:
- agent: Agent, Task, Message types
- session: Session management
- team: Multi-agent collaboration
- evolution: Self-improvement engine
"""
from .agent import (
    AgentRole,
    TaskStatus,
    MessageRole,
    AgentConfig,
    Task,
    TaskResult,
    Message,
    DecompositionResult,
    TeamEvent,
)
from .session import SessionManager, SessionContext, SessionConfig, SessionMetrics
from .team import TeamManager, TeamConfig, WorkerInfo, WorkerStatus, Inbox, InboxMessage
from .evolution import (
    EvolutionEngine,
    EvolutionTrigger,
    EvolutionEvent,
    EvolutionResult,
    DetectedPattern,
    SkillTemplate,
)

__all__ = [
    # Agent
    "AgentRole",
    "TaskStatus",
    "MessageRole",
    "AgentConfig",
    "Task",
    "TaskResult",
    "Message",
    "DecompositionResult",
    "TeamEvent",
    # Session
    "SessionManager",
    "SessionContext",
    "SessionConfig",
    "SessionMetrics",
    # Team
    "TeamManager",
    "TeamConfig",
    "WorkerInfo",
    "WorkerStatus",
    "Inbox",
    "InboxMessage",
    # Evolution
    "EvolutionEngine",
    "EvolutionTrigger",
    "EvolutionEvent",
    "EvolutionResult",
    "DetectedPattern",
    "SkillTemplate",
]