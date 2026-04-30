"""Main agent implementation using LangGraph - 轻量级核心循环"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool, BaseTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from minicode.agent.state import AgentState
from minicode.tools.registry import ALL_TOOLS
from minicode.services.model_provider import create_provider
from minicode.utils.system_prompt import get_system_prompt
from minicode.tools.permission_tools import bash_validator, check_permission

# Import Memory Layer for system prompt injection
try:
    from minicode.agent.memory import get_memory_layer
    HAS_MEMORY_LAYER = True
except ImportError:
    HAS_MEMORY_LAYER = False


WORKDIR = Path.cwd()

# 工具映射用于快速查找
TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}
TOOL_NODE = ToolNode(ALL_TOOLS, handle_tool_errors=True)

# ============ MCP 动态工具支持 ============
_MCP_DYNAMIC_TOOLS: list[BaseTool] = []
_MCP_TOOL_NODE: Optional[ToolNode] = None


def refresh_mcp_tools() -> int:
    """刷新 MCP 动态工具（从 langchain-mcp-adapters）

    调用此函数会重新从已连接的 MCP 服务器获取工具，
    并更新 TOOL_MAP 和重新创建 TOOL_NODE。

    Returns:
        获取到的工具数量
    """
    global _MCP_DYNAMIC_TOOLS, _MCP_TOOL_NODE, TOOL_MAP, TOOL_NODE

    try:
        from minicode.tools.mcp_tools import get_mcp_client
        client = get_mcp_client()

        # 获取 MCP 工具
        new_tools = client.get_tools()

        if new_tools:
            _MCP_DYNAMIC_TOOLS = new_tools

            # 更新全局工具映射
            TOOL_MAP = {t.name: t for t in ALL_TOOLS}
            for t in _MCP_DYNAMIC_TOOLS:
                TOOL_MAP[t.name] = t

            # 重新创建工具节点（包含 MCP 工具）
            TOOL_NODE = ToolNode(ALL_TOOLS + _MCP_DYNAMIC_TOOLS, handle_tool_errors=True)

            # 重置模型以包含新工具
            reset_for_mcp_refresh()

            return len(new_tools)
    except Exception as e:
        print(f"[MCP] Failed to refresh tools: {e}")

    return 0


def get_all_tools() -> list[BaseTool]:
    """获取所有可用工具（包括 MCP 动态工具）"""
    return ALL_TOOLS + _MCP_DYNAMIC_TOOLS


def get_tool_map() -> dict[str, BaseTool]:
    """获取工具映射"""
    return TOOL_MAP


def reset_for_mcp_refresh():
    """在刷新 MCP 工具后重置 AgentGraphBuilder"""
    builder = AgentGraphBuilder.get_instance()
    if builder:
        builder.reset()


class BashSecurityValidator:
    """简单的 Bash 命令安全验证"""
    VALIDATORS = [
        ("shell_metachar", r"[;&|`$]"),
        ("sudo", r"\bsudo\b"),
        ("rm_rf", r"\brm\s+(-[a-zA-Z]*)?r"),
        ("cmd_substitution", r"\$\("),
        ("ifs_injection", r"\bIFS\s*="),
    ]

    def validate(self, command: str) -> list[tuple[str, str]]:
        failures = []
        for name, pattern in self.VALIDATORS:
            if re.search(pattern, command):
                failures.append((name, pattern))
        return failures


bash_validator = BashSecurityValidator()


class AgentGraphBuilder:
    """构建 Agent Graph 的 Builder"""
    _instance: Optional["AgentGraphBuilder"] = None

    def __init__(
        self,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-7",
    ):
        self.model_provider = model_provider
        self.model_name = model_name
        self._model = None
        self._model_with_tools = None

    @classmethod
    def get_instance(cls) -> "AgentGraphBuilder":
        return cls._instance

    @property
    def model(self):
        if self._model is None:
            self._model = create_provider(
                provider=self.model_provider,
                model=self.model_name,
            ).client
        return self._model

    @property
    def model_with_tools(self):
        if self._model_with_tools is None:
            # 绑定所有工具（包括 MCP 动态工具）
            all_tools = get_all_tools()
            self._model_with_tools = self.model.bind_tools(all_tools)
        return self._model_with_tools

    def reset(self):
        """重置模型实例（用于切换模型或刷新工具时）"""
        self._model = None
        self._model_with_tools = None


def _build_system_message(state: Optional[AgentState] = None) -> str:
    """构建系统提示 - 支持记忆层注入"""
    base_prompt = get_system_prompt(WORKDIR)

    # 如果有 AgentState，尝试注入记忆层
    if state and HAS_MEMORY_LAYER:
        parts = [base_prompt]

        # 静态记忆: 用户偏好、项目配置
        if "static_memory" in state and state["static_memory"]:
            parts.append(state["static_memory"])

        # 动态记忆: 当前会话状态
        if "session_context" in state and state["session_context"]:
            parts.append(state["session_context"])

        # 事件记忆: 相关经验
        if "episodic_memory" in state and state["episodic_memory"]:
            parts.append(state["episodic_memory"])

        return "\n\n".join(parts)

    return base_prompt


def call_model(state: AgentState) -> dict:
    """调用 LLM 进行推理 - 核心节点"""
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}

    # 构建系统提示 - 传入 state 以便注入记忆
    system_msg = SystemMessage(content=_build_system_message(state))
    messages_with_system = [system_msg] + list(messages)

    # 获取环境变量中的模型配置
    provider = os.environ.get("MODEL_PROVIDER", "anthropic")
    name = os.environ.get("MODEL_NAME", "claude-sonnet-4-7")

    builder = AgentGraphBuilder.get_instance()
    if not builder or builder.model_provider != provider:
        builder = AgentGraphBuilder(provider, name)

    response = builder.model_with_tools.invoke(messages_with_system)
    return {"messages": [response]}


def execute_tools(state: AgentState) -> dict:
    """执行工具 - 核心节点"""
    messages = state.get("messages", [])
    if not messages:
        return {"messages": [], "tool_messages": []}

    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": [], "tool_messages": []}

    tool_calls = last_message.tool_calls
    tool_messages = []

    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc.get("args", {}) or {}
        tool_call_id = tc.get("id", "")

        # Bash 权限检查
        if tool_name == "bash_tool":
            command = tool_args.get("command", "")
            allowed, reason = check_permission(command, "bash_tool")
            if not allowed:
                tool_messages.append(
                    ToolMessage(content=f"[Permission Denied]: {reason}", tool_call_id=tool_call_id)
                )
                continue

        # 执行工具
        if tool_name in TOOL_MAP:
            try:
                result = TOOL_NODE.invoke({"messages": [last_message]})
                if "messages" in result:
                    for msg in result["messages"]:
                        if isinstance(msg, ToolMessage):
                            tool_messages.append(msg)
            except Exception as e:
                tool_messages.append(
                    ToolMessage(content=f"[Error] {e}", tool_call_id=tool_call_id)
                )
        else:
            tool_messages.append(
                ToolMessage(content=f"[Error] Unknown tool: {tool_name}", tool_call_id=tool_call_id)
            )

    return {"messages": tool_messages, "tool_messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """判断是否继续（工具调用）还是结束"""
    messages = state.get("messages", [])
    if not messages:
        return END

    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return END


def create_agent_graph(
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-7",
    use_checkpoint: bool = False,
):
    """创建轻量级 Agent Graph"""
    builder = AgentGraphBuilder(model_provider, model_name)
    AgentGraphBuilder._instance = builder

    workflow = StateGraph(AgentState)

    # 核心节点：只保留 agent 和 tools
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", execute_tools)

    # 边：agent → tools(如果需要) → agent → ...
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")

    checkpointer = MemorySaver() if use_checkpoint else None

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=None,  # 工具自动执行
    )


# 别名用于向后兼容
create_agent_graph_stream = create_agent_graph
create_agent_graph_async = create_agent_graph