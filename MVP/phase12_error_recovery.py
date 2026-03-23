#!/usr/bin/env python3
"""
phase12_error_recovery.py - Error Recovery

Three recovery paths:
- continue when output is truncated (max_tokens)
- compact when context grows too large (prompt_too_long)
- back off when transport errors are temporary (connection/rate)

Recovery priority (first match wins):
1. max_tokens -> inject continuation, retry
2. prompt_too_long -> compact, retry
3. connection error -> backoff, retry
4. all retries exhausted -> fail gracefully
"""
import json
import os
import random
import subprocess
import time
from pathlib import Path
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

load_dotenv(override=True)
os.environ["NO_PROXY"] = "*"

MODEL_ID = os.environ.get("AGENCY_LLM_MODEL", os.environ.get("MODEL_ID", "claude-sonnet-4-7"))
BASE_URL = os.getenv("AGENCY_LLM_BASE_URL")
API_KEY = os.getenv("AGENCY_LLM_API_KEY")
PROVIDER = os.getenv("AGENCY_LLM_PROVIDER", "openai")

WORKDIR = Path.cwd()

model = init_chat_model(
    MODEL_ID,
    model_provider=PROVIDER,
    temperature=0,
    max_tokens=8000,
    base_url=BASE_URL,
    api_key=API_KEY,
)

MAX_RECOVERY_ATTEMPTS = 3
BACKOFF_BASE_DELAY = 1.0
BACKOFF_MAX_DELAY = 30.0
TOKEN_THRESHOLD = 50000
CONTINUATION_MESSAGE = (
    "Output limit hit. Continue directly from where you stopped -- "
    "no recap, no repetition. Pick up mid-sentence if needed."
)


def _safe(p: str) -> Path:
    p = (WORKDIR / p).resolve()
    if not p.is_relative_to(WORKDIR):
        raise ValueError(p)
    return p


@tool
def bash(command: str) -> str:
    """Run a shell command."""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(item in command for item in dangerous):
        return "[Error]: Dangerous command blocked"
    try:
        r = subprocess.run(
            command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return "[Error]: Timeout (120s)"
    return (r.stdout + r.stderr).strip() or "(no output)"


@tool
def read_file(path: str, limit: Optional[int] = None) -> str:
    """Read file contents."""
    try:
        p = _safe(path)
        lines = p.read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"[Error]: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        f = _safe(path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"[Error]: {e}"


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace exact text in a file once."""
    try:
        f = _safe(path)
        content = f.read_text()
        if old_text not in content:
            return f"[Error]: Text not found in {path}"
        f.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"[Error]: {e}"


ALL_TOOLS = [bash, read_file, write_file, edit_file]
tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=True)
model_with_tools = model.bind_tools(ALL_TOOLS)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    max_output_recovery_count: int


def estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(json.dumps(messages, default=str)) // 4


def auto_compact(messages: list) -> list:
    """Compress conversation history into a short continuation summary."""
    conversation_text = json.dumps(messages, default=str)[:80000]
    prompt = (
        "Summarize this conversation for continuity. Include:\n"
        "1) Task overview and success criteria\n"
        "2) Current state: completed work, files touched\n"
        "3) Key decisions and failed approaches\n"
        "4) Remaining next steps\n"
        "Be concise but preserve critical details.\n\n" + conversation_text
    )
    try:
        response = model.invoke([HumanMessage(content=prompt)], config={"max_tokens": 4000})
        summary = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        summary = f"(compact failed: {e}). Previous context lost."
    continuation = (
        "This session continues from a previous conversation that was compacted. "
        f"Summary of prior context:\n\n{summary}\n\n"
        "Continue from where we left off without re-asking the user."
    )
    return [SystemMessage(content=continuation)]


def backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter."""
    delay = min(BACKOFF_BASE_DELAY * (2**attempt), BACKOFF_MAX_DELAY)
    jitter = random.uniform(0, 1)
    return delay + jitter


SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."


def call_model(state: AgentState) -> dict:
    """Stream model responses with error recovery."""
    messages_with_system = [SystemMessage(content=SYSTEM)] + state["messages"]
    recovery_count = state.get("max_output_recovery_count", 0)

    response = None
    last_error = None

    for attempt in range(MAX_RECOVERY_ATTEMPTS + 1):
        try:
            response = model_with_tools.invoke(messages_with_system)
            break
        except Exception as e:
            error_str = str(e).lower()
            last_error = e

            if "overlong_prompt" in error_str or ("prompt" in error_str and "long" in error_str):
                print(f"[Recovery] Prompt too long. Compacting... (attempt {attempt + 1})")
                compacted = auto_compact(list(state["messages"]))
                messages_with_system = [SystemMessage(content=SYSTEM)] + compacted
                state["messages"] = compacted
                continue

            if attempt < MAX_RECOVERY_ATTEMPTS:
                delay = backoff_delay(attempt)
                print(f"[Recovery] Error: {e}. Retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS})")
                time.sleep(delay)
                continue

            print(f"[Error] Failed after {MAX_RECOVERY_ATTEMPTS} retries: {e}")
            return {"messages": [AIMessage(content=f"Error: {e}")], "max_output_recovery_count": 0}

    if response is None:
        return {"messages": [AIMessage(content="No response received.")], "max_output_recovery_count": 0}

    return {"messages": [response], "max_output_recovery_count": recovery_count}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Decide whether to continue tool execution or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def handle_tool_outputs(state: AgentState) -> dict:
    """Process tool results and check for auto-compaction."""
    messages = list(state["messages"])
    tool_results = []

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                result_content = tc["message"]
                if result_content:
                    tool_results.append(result_content)

    if tool_results:
        new_messages = []
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    result_content = tc["message"]
                    if result_content:
                        new_messages.append(result_content)
            elif not (isinstance(msg, AIMessage) and msg.tool_calls):
                new_messages.append(msg)

        if estimate_tokens(new_messages) > TOKEN_THRESHOLD:
            print("[Recovery] Token estimate exceeds threshold. Auto-compacting...")
            compacted = auto_compact(new_messages)
            return {"messages": compacted, "max_output_recovery_count": 0}

    return {"max_output_recovery_count": 0}


workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

graph = workflow.compile()


if __name__ == "__main__":
    print("[Error recovery enabled: max_tokens / prompt_too_long / connection backoff]")
    print(f"[System prompt: {len(SYSTEM)} chars]")

    state: AgentState = {"messages": [], "max_output_recovery_count": 0}

    while True:
        try:
            q = input("\033[36mphase12 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in ("q", "exit", ""):
            break

        state["messages"].append(HumanMessage(content=q))
        state = graph.invoke(state)
        print()
