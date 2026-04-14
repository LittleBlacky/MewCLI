"""Agent runner - orchestrates the agent execution."""
import asyncio
from typing import Any, AsyncIterator, Optional

from minicode.agent.graph import create_agent_graph
from minicode.agent.state import AgentState
from minicode.services.checkpoint import create_checkpointer


class AgentRunner:
    """Main agent runner."""

    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-7",
        use_checkpoint: bool = False,
        db_path: Optional[str] = None,
    ):
        self.graph = create_agent_graph(model_provider, model_name)
        self.checkpointer = create_checkpointer(use_checkpoint, db_path)

    async def run(self, messages: list, thread_id: str = "default") -> dict:
        """Run agent with messages."""
        config = {"configurable": {"thread_id": thread_id}}
        if self.checkpointer:
            config["configurable"]["checkpoint_id"] = thread_id

        initial_state: AgentState = {
            "messages": messages,
            "todo_items": [],
            "rounds_since_todo_update": 0,
            "execution_steps": [],
            "evaluation_score": 0.0,
            "tool_messages": [],
            "task_items": [],
            "pending_tasks": [],
            "has_compacted": False,
            "last_summary": "",
            "recent_files": [],
            "compact_requested": False,
            "compact_focus": None,
            "mode": "default",
            "permission_rules": [],
            "consecutive_denials": 0,
            "teammates": {},
            "completed_results": [],
            "inbox_notifications": [],
            "pending_requests": [],
            "pending_background_tasks": [],
            "completed_notifications": [],
            "worktree_events": [],
            "active_worktrees": [],
            "task_type": "",
            "matched_skill": None,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
            "max_output_recovery_count": 3,
            "error_recovery_count": 0,
            "scheduled_notifications": [],
            "active_schedules": [],
        }

        result = await self.graph.ainvoke(initial_state, config)
        return result

    async def stream(self, messages: list, thread_id: str = "default") -> AsyncIterator[str]:
        """Stream agent responses."""
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: AgentState = {
            "messages": messages,
            "todo_items": [],
            "rounds_since_todo_update": 0,
            "execution_steps": [],
            "evaluation_score": 0.0,
            "tool_messages": [],
            "task_items": [],
            "pending_tasks": [],
            "has_compacted": False,
            "last_summary": "",
            "recent_files": [],
            "compact_requested": False,
            "compact_focus": None,
            "mode": "default",
            "permission_rules": [],
            "consecutive_denials": 0,
            "teammates": {},
            "completed_results": [],
            "inbox_notifications": [],
            "pending_requests": [],
            "pending_background_tasks": [],
            "completed_notifications": [],
            "worktree_events": [],
            "active_worktrees": [],
            "task_type": "",
            "matched_skill": None,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
            "max_output_recovery_count": 3,
            "error_recovery_count": 0,
            "scheduled_notifications": [],
            "active_schedules": [],
        }

        async for event in self.graph.astream(initial_state, config):
            if isinstance(event, dict) and "messages" in event:
                for msg in event["messages"]:
                    yield str(msg)
            else:
                yield str(event)
