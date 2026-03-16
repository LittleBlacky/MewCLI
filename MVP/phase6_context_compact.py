#!/usr/bin/env python3
import os
import json
import subprocess
from typing import TypedDict, List
from pathlib import Path
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    AIMessageChunk,
    SystemMessage,
)


# =====================
# ENV
# =====================
load_dotenv()

os.environ["NO_PROXY"] = "*"

MODEL_ID = os.environ["AGENCY_LLM_MODEL"]
BASE_URL = os.getenv("AGENCY_LLM_BASE_URL")
API_KEY = os.getenv("AGENCY_LLM_API_KEY")
PROVIDER = os.getenv("AGENCY_LLM_PROVIDER", "openai")

WORKDIR = Path.cwd()

CONTEXT_LIMIT = 500
KEEP_LAST_N = 12


# =====================
# LLM
# =====================
llm = init_chat_model(
    model=MODEL_ID,
    model_provider=PROVIDER,
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0,
)


# =====================
# TOOLS
# =====================


def safe_path(path_str: str) -> Path:
    path = (WORKDIR / path_str).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError("Path escapes workspace")
    return path


@tool
def read_file(path: str) -> str:
    """Read file content from workspace path."""
    try:
        return safe_path(path).read_text()
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in workspace."""
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"


@tool
def bash(command: str) -> str:
    """Run bash command inside workspace."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return (result.stdout + result.stderr).strip() or "(no output)"
    except Exception as e:
        return f"Error: {e}"


TOOLS = [read_file, write_file, bash]


# Tool-enabled LLM
llm_with_tools = llm.bind_tools(TOOLS)


# =====================
# STATE
# =====================
class AgentState(TypedDict):
    messages: List


# =====================
# NODES
# =====================


def micro_compact_node(state: AgentState):
    """Keep only recent messages for context control."""
    messages = state["messages"]

    if len(messages) > KEEP_LAST_N:
        print(f"截取最近 {KEEP_LAST_N} 条上下文")
        messages = messages[-KEEP_LAST_N:]

    return {"messages": messages}


def should_compact(state: AgentState):
    """Decide whether to compact context."""
    size = len(json.dumps([str(m) for m in state["messages"]]))
    return "compact" if size > CONTEXT_LIMIT else "continue"


def summarize_node(state: AgentState):
    """Summarize conversation when context is too large."""

    messages = state["messages"]

    summary_prompt = [
        SystemMessage(content="Summarize the conversation for continuation."),
        HumanMessage(content=str(messages)),
    ]
    print("压缩上下文: ")
    summary = llm.invoke(summary_prompt)
    print(f"总结内容：{summary}")
    return {"messages": [HumanMessage(content=f"[SUMMARY]\n{summary.content}")]}


def agent_node(state: AgentState):
    """Main reasoning node with tool calling enabled."""
    response = None
    for chunk in llm_with_tools.stream(state["messages"]):
        if isinstance(chunk, AIMessageChunk):
            if chunk.content:
                print(chunk.content, end="", flush=True)
            if response is None:
                response = chunk
            else:
                response = response + chunk
    print()
    if response is None:
        response = AIMessage(content=response)
    return {"messages": [response]}


# =====================
# ROUTER
# =====================


def should_use_tool(state: AgentState):
    """Check if last message contains tool calls."""
    last_msg = state["messages"][-1]

    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool"
    return "end"


# =====================
# GRAPH
# =====================

builder = StateGraph(AgentState)

builder.add_node("micro_compact", micro_compact_node)
builder.add_node("summarize", summarize_node)
builder.add_node("agent", agent_node)
builder.add_node("tool", ToolNode(TOOLS))

builder.set_entry_point("micro_compact")

# context control
builder.add_conditional_edges(
    "micro_compact", should_compact, {"compact": "summarize", "continue": "agent"}
)

# tool routing
builder.add_conditional_edges("agent", should_use_tool, {"tool": "tool", "end": END})

builder.add_edge("tool", "agent")
builder.add_edge("summarize", "agent")

graph = builder.compile()


# =====================
# CLI
# =====================


def run():
    state: AgentState = {
        "messages": [
            SystemMessage(content="You are a coding agent. Use tools when needed.")
        ]
    }

    while True:
        try:
            query = input("\033[36ms06 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip() in ("q", "exit", ""):
            break
        state["messages"].append(HumanMessage(content=query))
        state = graph.invoke(state)
        print()


if __name__ == "__main__":
    run()
