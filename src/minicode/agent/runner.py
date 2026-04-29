"""Agent runner - orchestrates the agent execution."""
import asyncio
import os
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from minicode.agent.graph import create_agent_graph, create_agent_graph_stream
from minicode.agent.state import AgentState
from minicode.services.checkpoint import CheckpointManager
from minicode.tools.hook_tools import get_hook_manager


class AgentRunner:
    """Main agent runner with streaming support."""

    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-7",
        use_checkpoint: bool = False,
        db_path: Optional[str] = None,
        workdir: Optional[Path] = None,
    ):
        self.model_provider = model_provider
        self.model_name = model_name
        self.use_checkpoint = use_checkpoint
        self.db_path = db_path
        self.workdir = workdir or Path.cwd()

        self.checkpoint_manager = CheckpointManager(
            use_sqlite=bool(db_path),
            db_path=db_path,
        )

        self.graph = create_agent_graph(
            model_provider=model_provider,
            model_name=model_name,
            use_checkpoint=use_checkpoint,
        )
        self.graph_stream = create_agent_graph_stream(
            model_provider=model_provider,
            model_name=model_name,
            use_checkpoint=use_checkpoint,
        )

        hook_manager = get_hook_manager()
        hook_result = hook_manager.run_hooks("SessionStart", {
            "model_provider": model_provider,
            "model_name": model_name,
            "thread_id": "default",
        })
        if hook_result["messages"]:
            for msg in hook_result["messages"]:
                print(f"[SessionStart] {msg}")

    def _get_initial_state(self, messages: list) -> AgentState:
        """Get initial agent state."""
        return {
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

    async def run(self, messages: list, thread_id: str = "default") -> dict:
        """Run agent with messages (non-streaming)."""
        config = self.checkpoint_manager.get_session_config(thread_id)

        initial_state = self._get_initial_state(messages)

        result = await self.graph.ainvoke(initial_state, config)
        return result

    async def stream(self, messages: list, thread_id: str = "default") -> AsyncIterator[str]:
        """Stream agent responses token by token."""
        config = self.checkpoint_manager.get_session_config(thread_id)

        initial_state = self._get_initial_state(messages)

        async for event in self.graph_stream.astream(initial_state, config):
            if isinstance(event, dict):
                if "messages" in event:
                    for msg in event["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            yield msg.content
                        elif hasattr(msg, "__str__"):
                            yield str(msg)
                elif "tool_messages" in event:
                    for msg in event["tool_messages"]:
                        if hasattr(msg, "content"):
                            yield f"\n> {msg.content[:200]}"
            else:
                yield str(event)

    async def run_with_user_input(
        self,
        user_input: str,
        thread_id: str = "default",
        resume_from: Optional[str] = None,
    ) -> str:
        """Run agent with a single user input, handling interrupts."""
        from langgraph.types import Command

        config = self.checkpoint_manager.get_session_config(thread_id)

        if resume_from:
            input_state = Command(resume=resume_from)
        else:
            input_state = {"messages": [HumanMessage(content=user_input)]}

        final_response = ""
        try:
            async for event in self.graph_stream.astream(input_state, config):
                if isinstance(event, dict):
                    if "__interrupt__" in event:
                        for interrupt_info in event["__interrupt__"]:
                            yield str(interrupt_info.value)
                    elif "messages" in event:
                        for msg in event["messages"]:
                            if hasattr(msg, "content") and msg.content:
                                final_response += msg.content
                else:
                    final_response += str(event)
        except Exception as e:
            return f"[Error]: {e}"

        return final_response

    def get_session_state(self, thread_id: str = "default") -> Optional[dict]:
        """Get the current state of a session."""
        config = self.checkpoint_manager.get_session_config(thread_id)
        return self.graph.get_state(config)

    def clear_session(self, thread_id: str = "default") -> None:
        """Clear a session's checkpoint."""
        self.checkpoint_manager.clear_session(thread_id)


async def run_interactive(
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-7",
    thread_id: str = "default",
) -> None:
    """Run an interactive REPL session."""
    import sys

    runner = AgentRunner(
        model_provider=model_provider,
        model_name=model_name,
        use_checkpoint=True,
    )

    print(f"MiniCode Interactive Agent")
    print(f"Model: {model_name}")
    print(f"Thread: {thread_id}")
    print("Type 'exit' or 'q' to quit\n")

    messages = []

    while True:
        try:
            user_input = input(f"\033[36m{thread_id} >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if user_input.strip().lower() in ("q", "exit", ""):
            break

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            if cmd == "/clear":
                messages = []
                print("History cleared")
                continue
            elif cmd == "/history":
                print(f"Messages: {len(messages)}")
                continue
            elif cmd == "/state":
                state = runner.get_session_state(thread_id)
                if state:
                    print(f"Session active with {len(state.values.get('messages', []))} messages")
                else:
                    print("No active session")
                continue

        messages.append(HumanMessage(content=user_input))

        print("\n[Processing...]\n")

        try:
            result = await runner.run(messages, thread_id)
            if "messages" in result:
                response_msgs = result["messages"]
                for msg in response_msgs:
                    if hasattr(msg, "content") and msg.content:
                        print(f"\033[32m{msg.content}\033[0m")
        except Exception as e:
            print(f"[Error]: {e}")
            continue

        print()


if __name__ == "__main__":
    asyncio.run(run_interactive())
