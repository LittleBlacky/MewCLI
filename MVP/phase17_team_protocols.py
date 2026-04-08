#!/usr/bin/env python3
from __future__ import annotations
"""
phase17_team_protocols.py - Team Protocols with LangGraph Native Patterns

Structured handshakes between models using request_id correlation.
Implements shutdown protocol and plan approval protocol.

    Shutdown FSM: pending -> approved | rejected
    Plan approval FSM: pending -> approved | rejected

Key insight: "One request/response shape can support multiple kinds of team workflow.
Protocol requests are structured workflow objects, not normal free-form chat."

LangGraph native patterns:
- MemorySaver checkpointer for session persistence
- State updates for protocol tracking
- RequestStore for durable protocol state with correlation IDs
"""
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
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
STORAGE_DIR = WORKDIR / ".mini-agent-cli"
TEAM_DIR = STORAGE_DIR / "team"
INBOX_DIR = TEAM_DIR / "inbox"
REQUESTS_DIR = TEAM_DIR / "requests"

model = init_chat_model(
    MODEL_ID,
    model_provider=PROVIDER,
    temperature=0,
    max_tokens=8000,
    base_url=BASE_URL,
    api_key=API_KEY,
)

VALID_MSG_TYPES = {
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval",
    "plan_approval_response",
}


# ========== MessageBus ==========

class MessageBus:
    """JSONL inbox per teammate for protocol communication."""

    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: dict = None,
    ) -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"[Error]: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        if extra:
            msg.update(extra)
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                messages.append(json.loads(line))
        inbox_path.write_text("")
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        count = 0
        for name in teammates:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"


BUS = MessageBus(INBOX_DIR)


# ========== RequestStore ==========

class RequestStore:
    """
    Durable request records for protocol workflows.
    Keeps one JSON file per request_id under .mini-agent-cli/team/requests/.
    Protocol state survives to allow inspection, resume, or reconciliation.
    """

    def __init__(self, base_dir: Path):
        self.dir = base_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, request_id: str) -> Path:
        return self.dir / f"{request_id}.json"

    def create(self, record: dict) -> dict:
        request_id = record["request_id"]
        with self._lock:
            self._path(request_id).write_text(json.dumps(record, indent=2))
        return record

    def get(self, request_id: str) -> dict | None:
        path = self._path(request_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def update(self, request_id: str, updates: dict) -> dict:
        record = self.get(request_id)
        if not record:
            raise ValueError(f"Request {request_id} not found")
        record.update(updates)
        with self._lock:
            self._path(request_id).write_text(json.dumps(record, indent=2))
        return record

    def list_all(self) -> list[dict]:
        records = []
        for p in self.dir.glob("*.json"):
            records.append(json.loads(p.read_text()))
        return records

    def delete(self, request_id: str) -> bool:
        path = self._path(request_id)
        if path.exists():
            path.unlink()
            return True
        return False


REQUESTS = RequestStore(REQUESTS_DIR)


# ========== Base Tool Implementations ==========

def _safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def _run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    if any(d in command for d in dangerous):
        return "[Error]: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "[Error]: Timeout (120s)"


def _run_read(path: str, limit: int = None) -> str:
    try:
        lines = _safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"[Error]: {e}"


def _run_write(path: str, content: str) -> str:
    try:
        fp = _safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"[Error]: {e}"


def _run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = _safe_path(path)
        c = fp.read_text()
        if old_text not in c:
            return f"[Error]: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"[Error]: {e}"


# ========== Agent State ==========

class AgentState(TypedDict):
    """Agent state with langgraph native checkpoint support."""
    messages: Annotated[list, add_messages]
    pending_requests: list[dict]  # LangGraph native: track pending protocol requests
    inbox_notifications: list[dict]  # LangGraph native: incoming protocol messages


# ========== Tool Functions ==========

@tool
def bash_tool(command: str) -> str:
    """Run a shell command."""
    return _run_bash(command)


@tool
def read_file(path: str, limit: Optional[int] = None) -> str:
    """Read file contents."""
    return _run_read(path, limit)


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    return _run_write(path, content)


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace exact text in a file."""
    return _run_edit(path, old_text, new_text)


@tool
def send_message(to: str, content: str, msg_type: str = "message") -> str:
    """Send a message to a teammate's inbox."""
    return BUS.send("lead", to, content, msg_type)


@tool
def read_inbox() -> str:
    """Read and drain your inbox."""
    return json.dumps(BUS.read_inbox("lead"), indent=2)


@tool
def broadcast(content: str) -> str:
    """Broadcast to all teammates."""
    return BUS.broadcast("lead", content, ["alice", "bob"])


@tool
def shutdown_request(to: str, reason: str = "") -> str:
    """
    Send a shutdown request to a teammate.
    Uses request_id correlation for the handshake.
    """
    request_id = str(uuid.uuid4())[:8]
    REQUESTS.create({
        "request_id": request_id,
        "type": "shutdown_request",
        "from": "lead",
        "to": to,
        "reason": reason,
        "status": "pending",
        "created_at": time.time(),
    })
    BUS.send("lead", to, json.dumps({
        "request_id": request_id,
        "reason": reason,
    }), "shutdown_request", {"request_id": request_id})
    return f"Shutdown request sent to {to} (request_id={request_id})"


@tool
def shutdown_response(request_id: str, approve: bool) -> str:
    """
    Respond to a shutdown request.
    Teammates use this to approve or reject shutdown.
    """
    record = REQUESTS.get(request_id)
    if not record:
        return f"[Error]: Request {request_id} not found"
    REQUESTS.update(request_id, {
        "status": "approved" if approve else "rejected",
        "approved": approve,
        "responded_at": time.time(),
    })
    return f"Shutdown response: {'approved' if approve else 'rejected'} for {request_id}"


@tool
def plan_approval(to: str, plan: str) -> str:
    """
    Submit a plan for approval to a teammate.
    Returns request_id for correlation.
    """
    request_id = str(uuid.uuid4())[:8]
    REQUESTS.create({
        "request_id": request_id,
        "type": "plan_approval",
        "from": "lead",
        "to": to,
        "plan": plan,
        "status": "pending",
        "created_at": time.time(),
    })
    BUS.send("lead", to, json.dumps({
        "request_id": request_id,
        "plan": plan,
    }), "plan_approval", {"request_id": request_id})
    return f"Plan approval request sent to {to} (request_id={request_id})"


@tool
def plan_approval_response(request_id: str, approve: bool, feedback: str = "") -> str:
    """
    Respond to a plan approval request.
    """
    record = REQUESTS.get(request_id)
    if not record:
        return f"[Error]: Request {request_id} not found"
    REQUESTS.update(request_id, {
        "status": "approved" if approve else "rejected",
        "approved": approve,
        "feedback": feedback,
        "responded_at": time.time(),
    })
    return f"Plan approval response: {'approved' if approve else 'rejected'} for {request_id}"


@tool
def get_request(request_id: str) -> str:
    """Get request details by ID."""
    record = REQUESTS.get(request_id)
    return json.dumps(record, indent=2) if record else f"[Error]: Request {request_id} not found"


@tool
def list_requests() -> str:
    """List all requests."""
    records = REQUESTS.list_all()
    return json.dumps(records, indent=2) if records else "No requests."


# Define tool list and tool node
agent_tools = [
    bash_tool, read_file, write_file, edit_file,
    send_message, read_inbox, broadcast,
    shutdown_request, shutdown_response,
    plan_approval, plan_approval_response,
    get_request, list_requests
]
tool_node = ToolNode(agent_tools, handle_tool_errors=True)
model_with_tools = model.bind_tools(agent_tools)


# ========== Graph Nodes ==========

SYSTEM_PROMPT = f"""You are a team lead at {WORKDIR}. Manage teammates with structured protocols.

Available protocol operations:
- shutdown_request(to, reason): Send shutdown request
- shutdown_response(request_id, approve): Respond to shutdown
- plan_approval(to, plan): Submit plan for approval
- plan_approval_response(request_id, approve, feedback): Respond to plan approval
- get_request(request_id): Get request details
- list_requests(): List all requests

Protocols use request_id correlation for durable handshakes.
LangGraph native: Checkpoint persistence, state-based protocol tracking.
"""


def call_model(state: AgentState) -> dict:
    """Call the model with current messages, draining inbox notifications.
    LangGraph native: uses state for protocol message injection."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    # Check for incoming protocol messages from state
    inbox_notifications = state.get("inbox_notifications", [])
    if inbox_notifications:
        for msg in inbox_notifications:
            msg_type = msg.get("type", "message")
            if msg_type in ("shutdown_response", "plan_approval_response"):
                request_id = msg.get("request_id", "")
                content = msg.get("content", "")
                try:
                    content_data = json.loads(content)
                    print(f"[Protocol] {msg_type} for {request_id}: {content_data}")
                except:
                    print(f"[Protocol] {msg_type}: {content}")
            else:
                print(f"[Inbox] {msg_type} from {msg.get('from')}: {msg.get('content', '')[:100]}")

    response = model_with_tools.invoke(messages)
    return {"messages": [response], "inbox_notifications": []}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Check if there are tool calls to execute."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


# Build the graph with checkpoint (LangGraph native)
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"tools": "tools", END: END}
)

# Compile with checkpoint for session persistence (LangGraph native)
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)


def get_session_config(thread_id: str) -> dict:
    """LangGraph native: Get session config for checkpointing."""
    return {"configurable": {"thread_id": thread_id}}


def run_agent(query: str, thread_id: str = "protocol_session_1") -> dict:
    """Run the agent with checkpoint support for session persistence."""
    config = get_session_config(thread_id)

    # Check for existing state
    existing = graph.get_state(config)
    existing_msgs = existing.values.get("messages", []) if existing else []
    existing_requests = existing.values.get("pending_requests", []) if existing else []

    # Check inbox for any new protocol messages
    inbox = BUS.read_inbox("lead")
    inbox_notifications = existing.values.get("inbox_notifications", []) if existing else []
    if inbox:
        inbox_notifications = inbox_notifications + inbox

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "pending_requests": existing_requests,
        "inbox_notifications": inbox_notifications,
    }

    for event in graph.stream(initial_state, config):
        node_name = list(event.keys())[0]
        if node_name == "agent":
            response = event[node_name]["messages"][-1]
            if hasattr(response, 'content') and response.content:
                print(f"\nAssistant: {response.content}")
        elif node_name == "tools":
            pass


if __name__ == "__main__":
    thread_id = "protocol_session_1"
    config = get_session_config(thread_id)

    # Resume from checkpoint
    existing = graph.get_state(config)
    if existing and existing.values.get("messages"):
        print(f"[Resuming session {thread_id} with {len(existing.values['messages'])} messages]\n")

    print("Team Protocols (phase17) - LangGraph Native Patterns")
    print("Features: Checkpoint persistence, state-based protocol tracking")
    print("Use shutdown_request and plan_approval for structured workflows")
    print("Type 'exit' or 'q' to quit, '/requests' to list protocol requests\n")

    while True:
        try:
            query = input(f"\033[36m{thread_id} >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        if query.strip() == "/requests":
            print(REQUESTS.list_all())
            continue
        run_agent(query, thread_id)