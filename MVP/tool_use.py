#!/usr/bin/env python3
"""
s02_tool_use_langgraph.py - LangGraph version of s02_tool_use.py
Tool dispatch + message normalization with LangGraph state machine.
Uses init_chat_model for LLM initialization.
"""
import os
import subprocess
from pathlib import Path
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# ----------------------------------------------------------------------
# Environment and model setup (init_chat_model)
# ----------------------------------------------------------------------
load_dotenv(override=True)
MODEL = os.getenv('AGENCY_LLM_MODEL')
PROVIDER = os.getenv('AGENCY_LLM_PROVIDER')
BASE_URL = os.getenv('AGENCY_LLM_BASE_URL')
API_KEY = os.getenv('AGENCY_LLM_API_KEY')

model = init_chat_model(
    MODEL,
    model_provider=PROVIDER,
    temperature=0,
    max_tokens=8000,
    base_url=BASE_URL,
    api_key=API_KEY,
)

WORKDIR = Path.cwd()

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."

# ----------------------------------------------------------------------
# Tool implementations (identical to original)
# ----------------------------------------------------------------------
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: Optional[int] = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# Concurrency safety classification (preserved as comment)
# CONCURRENCY_SAFE = {"read_file"}
# CONCURRENCY_UNSAFE = {"write_file", "edit_file"}

# ----------------------------------------------------------------------
# Define tools using @tool decorator (LangChain format)
# ----------------------------------------------------------------------
@tool
def bash_tool(command: str) -> str:
    """Run a shell command in the workspace."""
    return run_bash(command)


@tool
def read_file(path: str, limit: Optional[int] = None) -> str:
    """Read file contents. Optionally limit the number of lines returned."""
    return run_read(path, limit)


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    return run_write(path, content)


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace the first occurrence of old_text with new_text in a file."""
    return run_edit(path, old_text, new_text)


tools = [bash_tool, read_file, write_file, edit_file]
tool_map = {t.name: t for t in tools}

# Bind tools to model
model_with_tools = model.bind_tools(tools)

# ----------------------------------------------------------------------
# State definition
# ----------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ----------------------------------------------------------------------
# Message normalization (adapted to LangChain message objects)
# ----------------------------------------------------------------------
def normalize_messages(messages: list) -> list:
    """
    Clean up messages before sending to the model.
    - Ensure system prompt is first (as SystemMessage)
    - Ensure tool calls have matching tool results (insert placeholder if missing)
    - Merge consecutive same-role messages (LangChain handles alternation automatically,
      but we keep the logic for safety).
    """
    if not messages:
        return [SystemMessage(content=SYSTEM)]

    # Ensure SystemMessage at start
    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM)] + messages

    cleaned = []
    for msg in messages:
        # Convert any dict-style messages to LangChain objects if needed
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                cleaned.append(HumanMessage(content=content))
            elif role == "assistant":
                cleaned.append(AIMessage(content=content))
            elif role == "system":
                cleaned.append(SystemMessage(content=content))
            elif role == "tool":
                cleaned.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", "")
                ))
            else:
                cleaned.append(HumanMessage(content=str(content)))
        else:
            cleaned.append(msg)

    # Find tool_calls that lack a corresponding ToolMessage
    tool_call_ids_seen = set()
    for msg in cleaned:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_call_ids_seen.add(tc["id"])
        elif isinstance(msg, ToolMessage):
            tool_call_ids_seen.discard(msg.tool_call_id)

    # Add placeholder ToolMessages for missing results
    for missing_id in tool_call_ids_seen:
        cleaned.append(ToolMessage(
            content="(cancelled)",
            tool_call_id=missing_id
        ))

    # Merge consecutive messages of same role (LangChain doesn't strictly require this,
    # but we implement to be faithful to original behavior)
    merged = []
    for msg in cleaned:
        if not merged:
            merged.append(msg)
            continue
        prev = merged[-1]
        if type(prev) is type(msg):
            # Merge content (simplified: concatenate strings)
            if hasattr(prev, "content") and hasattr(msg, "content"):
                prev.content = f"{prev.content}\n{msg.content}"
            else:
                merged.append(msg)
        else:
            merged.append(msg)

    return merged


# ----------------------------------------------------------------------
# Graph nodes
# ----------------------------------------------------------------------
def call_model(state: AgentState) -> dict:
    """Invoke LLM with normalized messages."""
    normalized = normalize_messages(state["messages"])
    response = model_with_tools.invoke(normalized)
    return {"messages": [response]}


def execute_tools(state: AgentState) -> dict:
    """Execute tool calls from the last assistant message."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_obj = tool_map.get(tool_name)
        if tool_obj:
            print(f"> {tool_name}:")
            try:
                output = tool_obj.invoke(tool_args)
            except Exception as e:
                output = f"Error: {e}"
        else:
            output = f"Unknown tool: {tool_name}"

        print(output[:200])
        tool_messages.append(
            ToolMessage(content=output, tool_call_id=tool_call["id"])
        )

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Decide whether to continue tool execution or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


# ----------------------------------------------------------------------
# Build graph
# ----------------------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", execute_tools)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

graph = workflow.compile()

# ----------------------------------------------------------------------
# CLI loop (preserved original style)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    history = []  # Will hold LangChain message objects
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append(HumanMessage(content=query))

        # Run the graph
        result = graph.invoke({"messages": history})
        history = result["messages"]

        # Print final assistant response (text part)
        final_msg = history[-1]
        if isinstance(final_msg, AIMessage) and final_msg.content:
            print(final_msg.content)
        print()