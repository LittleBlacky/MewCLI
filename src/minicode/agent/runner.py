"""Agent Runner - 分层防御架构 + 记忆层"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, Optional

from langchain_core.messages import HumanMessage

from minicode.agent.graph import create_agent_graph
from minicode.agent.state import AgentState
from minicode.agent.session import (
    SessionManager,
    SessionConfig,
    get_session_manager,
    reset_session_manager,
)
from minicode.agent.memory import (
    MemoryLayer,
    MemoryEntry,
    get_memory_layer,
)
from minicode.services.checkpoint import CheckpointManager
from minicode.tools.hook_tools import get_hook_manager


class AgentRunner:
    """Agent 运行器 - 四层架构

    分层防御策略:
    1. Input Safety - 运行前预检+压缩
    2. Memory Layer - 检索+注入相关记忆
    3. Graph Execution - 轻量循环
    4. Output Protection - 过长输出保存文件
    5. Periodic Cleanup - 周期性压缩

    记忆层职责:
    - 检索相关记忆
    - 注入到系统提示
    - 自动保存任务记忆
    - 周期整合
    """

    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-7",
        use_checkpoint: bool = False,
        db_path: Optional[str] = None,
        workdir: Optional[Path] = None,
        session_config: Optional[SessionConfig] = None,
    ):
        self.model_provider = model_provider
        self.model_name = model_name
        self.use_checkpoint = use_checkpoint
        self.db_path = db_path
        self.workdir = workdir or Path.cwd()

        # 记忆层
        self.memory = get_memory_layer()

        # 会话管理器
        self.session = SessionManager(session_config)

        # 检查点管理器
        self.checkpoint_manager = CheckpointManager(
            use_sqlite=bool(db_path),
            db_path=db_path,
        )

        # Agent Graph
        self.graph = create_agent_graph(
            model_provider=model_provider,
            model_name=model_name,
            use_checkpoint=use_checkpoint,
        )

        # SessionStart hooks
        hook_manager = get_hook_manager()
        hook_result = hook_manager.run_hooks("SessionStart", {
            "model_provider": model_provider,
            "model_name": model_name,
            "thread_id": "default",
        })
        if hook_result["messages"]:
            for msg in hook_result["messages"]:
                print(f"[SessionStart] {msg}")

    def _get_initial_state(self, messages: list, injected_memories: str = "") -> AgentState:
        """获取初始状态"""
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
            "injected_memories": injected_memories,  # 注入的记忆
        }

    async def run(self, messages: list, thread_id: str = "default") -> dict:
        """运行 Agent - 四层架构

        Layer 1: Input Safety - 预检+压缩
        Layer 2: Memory Layer - 检索+注入记忆
        Layer 3: Graph Execution - 轻量执行
        Layer 4: Output Protection - 保护过长输出
        Layer 5: Periodic Cleanup - 周期性压缩
        """
        config = self.checkpoint_manager.get_session_config(thread_id)

        # Layer 1: Input Safety - 运行前预检
        safe_messages = self.session.preflight_check(messages)

        # Layer 2: Memory Layer - 检索相关记忆
        injected_memories = ""
        if messages:
            # 从最后一条用户消息提取查询
            last_user_msg = messages[-1] if isinstance(messages[-1], HumanMessage) else None
            if last_user_msg and hasattr(last_user_msg, "content"):
                query = last_user_msg.content[:200]  # 取前200字符作为查询
                injected_memories = self.memory.inject_memories(query)

        initial_state = self._get_initial_state(safe_messages, injected_memories)

        try:
            # Layer 3: Graph Execution
            result = await self.graph.ainvoke(initial_state, config)

            # Layer 4: Output Protection - 保护过长输出
            all_messages = list(result.get("messages", []))
            all_messages = self.session.protect_output(all_messages)
            result["messages"] = all_messages

            # Layer 5: Periodic Cleanup
            post_result = self.session.after_run(all_messages, had_error=False)

            if "compact" in post_result.get("actions", []):
                result["messages"] = post_result.get("messages", all_messages)

            return result

        except Exception as e:
            # Error Recovery
            if self._is_overflow_error(e):
                print(f"[Warning] Context overflow detected, attempting recovery...")

                state = self.graph.get_state(config)
                if state and "messages" in state.values:
                    current_messages = list(state.values["messages"])
                else:
                    current_messages = safe_messages

                compacted = self.session.compact(current_messages, aggressive=True)
                retry_state = self._get_initial_state(compacted)

                try:
                    result = await self.graph.ainvoke(retry_state, config)
                    result_messages = list(result.get("messages", []))
                    result_messages = self.session.protect_output(result_messages)
                    result["messages"] = result_messages
                    return result

                except Exception as retry_error:
                    print(f"[Error] Recovery failed: {retry_error}")
                    raise retry_error

            raise

    async def stream(self, messages: list, thread_id: str = "default") -> AsyncIterator[str]:
        """流式运行 Agent"""
        config = self.checkpoint_manager.get_session_config(thread_id)

        safe_messages = self.session.preflight_check(messages)
        injected_memories = ""
        if messages:
            last_user_msg = messages[-1] if isinstance(messages[-1], HumanMessage) else None
            if last_user_msg and hasattr(last_user_msg, "content"):
                query = last_user_msg.content[:200]
                injected_memories = self.memory.inject_memories(query)

        initial_state = self._get_initial_state(safe_messages, injected_memories)

        async for event in self.graph.astream(initial_state, config):
            if isinstance(event, dict):
                if "messages" in event:
                    for msg in event["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            yield msg.content
                elif "tool_messages" in event:
                    for msg in event["tool_messages"]:
                        if hasattr(msg, "content"):
                            yield f"\n> {msg.content[:200]}"
            else:
                yield str(event)

    def _is_overflow_error(self, error: Exception) -> bool:
        """判断是否是上下文溢出错误"""
        error_str = str(error).lower()
        overflow_indicators = [
            "context", "token", "maximum", "too long",
            "length", "exceeds", "context_length_exceeded",
        ]
        return any(indicator in error_str for indicator in overflow_indicators)

    # ========== Memory Layer API ==========

    def get_session_summary(self) -> dict:
        """获取会话摘要"""
        summary = self.session.get_summary()
        summary["memory_stats"] = self.memory.get_stats()
        return summary

    def get_memory(self) -> list:
        """获取记忆列表"""
        return self.memory.list_all()

    def save_memory(self, name: str, description: str, mem_type: str, content: str) -> str:
        """保存记忆"""
        return self.memory.save(name, content, mem_type, description)

    def search_memory(self, query: str, memory_type: Optional[str] = None) -> list[dict]:
        """搜索记忆"""
        entries = self.memory.retrieve(query, memory_type)
        return [
            {
                "name": e.name,
                "description": e.description,
                "type": e.memory_type,
                "content_preview": e.content[:200],
            }
            for e in entries
        ]

    def consolidate_memory(self) -> dict:
        """整合记忆"""
        return self.memory.consolidate()

    def compact_now(self) -> dict:
        """手动触发压缩"""
        state = self.get_session_state()
        if state and "messages" in state.values:
            messages = list(state.values["messages"])
            compacted = self.session.compact(messages)
            return {
                "original_count": len(messages),
                "compacted_count": len(compacted),
            }
        return {"error": "No session state"}

    def get_session_state(self, thread_id: str = "default") -> Optional[dict]:
        """获取会话状态"""
        config = self.checkpoint_manager.get_session_config(thread_id)
        return self.graph.get_state(config)

    def clear_session(self, thread_id: str = "default") -> None:
        """清除会话"""
        self.checkpoint_manager.clear_session(thread_id)
        self.session.reset()


async def run_interactive(
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-7",
    thread_id: str = "default",
) -> None:
    """交互式运行"""
    reset_session_manager()

    runner = AgentRunner(
        model_provider=model_provider,
        model_name=model_name,
        use_checkpoint=True,
    )

    print(f"MiniCode Interactive Agent")
    print(f"Model: {model_name}")
    print("Commands: /clear, /history, /memory, /search, /compact")
    print("-" * 50)

    messages = []

    while True:
        try:
            user_input = input(f"\033[36m{thread_id} >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()

            if cmd in ("/q", "/quit", "/exit"):
                break
            elif cmd == "/clear":
                messages = []
                print("History cleared")
                continue
            elif cmd == "/history":
                summary = runner.get_session_summary()
                print(f"Turns: {summary['total_turns']}, "
                      f"Tasks: {summary['tasks_completed']}, "
                      f"Memory: {summary.get('memory_stats', {}).get('total', 0)}")
                continue
            elif cmd == "/memory":
                mems = runner.get_memory()
                print(f"Memory entries: {len(mems)}")
                for m in mems[:5]:
                    print(f"  - [{m['type']}] {m['name']}")
                continue
            elif cmd == "/search":
                if len(parts) > 1:
                    results = runner.search_memory(parts[1])
                    print(f"Found {len(results)} memories:")
                    for r in results:
                        print(f"  - {r['name']}: {r['content_preview'][:50]}...")
                continue
            elif cmd == "/compact":
                result = runner.compact_now()
                print(f"Compacted: {result.get('original_count', 0)} -> {result.get('compacted_count', 0)}")
                continue
            elif cmd == "/consolidate":
                result = runner.consolidate_memory()
                print(f"Consolidated: deleted {len(result.get('deleted', []))}, remaining {result.get('remaining', 0)}")
                continue
            elif cmd == "/help":
                print("Commands: /clear, /history, /memory, /search <query>, /compact, /consolidate, /q")
                continue

        messages.append(HumanMessage(content=user_input))

        print("\n[Processing...]\n")

        try:
            result = await runner.run(messages, thread_id)
            response_msgs = result.get("messages", [])

            for msg in response_msgs:
                if hasattr(msg, "content") and msg.content:
                    print(f"\033[32m{msg.content}\033[0m")
        except Exception as e:
            print(f"[Error]: {e}")

        print()


if __name__ == "__main__":
    asyncio.run(run_interactive())