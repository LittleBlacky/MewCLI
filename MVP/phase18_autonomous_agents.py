#!/usr/bin/env python3
from __future__ import annotations
"""
phase18_autonomous_agents.py - Autonomous Agents

Idle cycle with task board polling, auto-claiming unclaimed tasks, and
identity re-injection after context compression.

    Teammate lifecycle:
    +-------+
    | spawn |
    +---+---+
        |
        v
    +-------+  tool_use    +-------+
    | WORK  | <----------- |  LLM  |
    +---+---+              +-------+
        |
        | stop_reason != tool_use
        v
    +--------+
    | IDLE   | poll every 5s for up to 60s
    +---+----+
        |
        +---> check inbox -> message? -> resume WORK
        +---> scan .mini-agent-cli/tasks/ -> unclaimed? -> claim -> resume WORK
        +---> timeout (60s) -> shutdown

Key insight: "An idle teammate can safely claim ready work instead of waiting
for every assignment from the lead."

LangGraph concepts:
- Use TaskManager for task board operations
- MessageBus for inbox communication
- Autonomous polling with idle timeout
- Identity re-injection after context compression
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
TASKS_DIR = STORAGE_DIR / "tasks"
POLL_INTERVAL = 5
IDLE_TIMEOUT = 60

model = init_chat_model(
    MODEL_ID,
    model_provider=PROVIDER,
    temperature=0,
    max_tokens=8000,
    base_url=BASE_URL,
    api_key=API_KEY,
)

VALID_MSG_TYPES = {
    "message", "broadcast", "shutdown_request", "shutdown_response",
    "plan_approval", "plan_approval_response",
}


# ========== MessageBus ==========

class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str, msg_type: str = "message", extra: dict = None) -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"[Error]: Invalid type '{msg_type}'"
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
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


BUS = MessageBus(INBOX_DIR)


# ========== TaskManager ==========

class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._next_id = self._max_id() + 1

    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json") if f.stem.split("_")[1].isdigit()]
        return max(ids) if ids else 0

    def _path(self, task_id: int) -> Path:
        return self.dir / f"task_{task_id}.json"

    def _load(self, task_id: int) -> dict:
        path = self._path(task_id)
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        self._path(task["id"]).write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> dict:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "owner": "",
            "blockedBy": [],
            "blocks": [],
        }
        self._save(task)
        self._next_id += 1
        return task

    def get(self, task_id: int) -> dict:
        return self._load(task_id)

    def update(self, task_id: int, status: str = None, owner: str = None, add_blocked_by: list = None, add_blocks: list = None) -> dict:
        task = self._load(task_id)
        if owner is not None:
            task["owner"] = owner
        if status:
            if status not in ("pending", "in_progress", "completed", "deleted"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
        self._save(task)
        return task

    def _clear_dependency(self, completed_id: int):
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)

    def list_all(self) -> list:
        return [json.loads(f.read_text()) for f in sorted(self.dir.glob("task_*.json"))]

    def find_unclaimed(self) -> list:
        """Find tasks that are pending with no owner."""
        return [t for t in self.list_all() if t.get("status") == "pending" and not t.get("owner")]

    def claim(self, task_id: int, owner: str) -> dict:
        """Claim a task for a specific owner."""
        task = self._load(task_id)
        if task.get("owner"):
            raise ValueError(f"Task {task_id} already claimed by {task['owner']}")
        return self.update(task_id, status="in_progress", owner=owner)


TASKS = TaskManager(TASKS_DIR)


# ========== TeammateManager ==========

class TeammateManager:
    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = self._load_config()
        self.threads = {}

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {"team_name": "default", "members": []}

    def _save_config(self):
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def _find_member(self, name: str) -> dict:
        for m in self.config["members"]:
            if m["name"] == name:
                return m
        return None

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find_member(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"[Error]: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save_config()
        thread = threading.Thread(target=self._autonomous_loop, args=(name, role, prompt), daemon=True)
        self.threads[name] = thread
        thread.start()
        return f"Spawned autonomous '{name}' (role: {role})"

    def _autonomous_loop(self, name: str, role: str, initial_prompt: str):
        """Autonomous teammate with idle polling."""
        identity_block = (
            f"You are '{name}', role: {role}, at {WORKDIR}. "
            "You find work autonomously when idle. Use tools to complete tasks."
        )
        messages = [{"role": "user", "content": initial_prompt}]
        idle_start = None
        max_work_turns = 50

        for turn in range(max_work_turns):
            # Check inbox first
            inbox = BUS.read_inbox(name)
            for msg in inbox:
                # Handle shutdown request
                if msg.get("type") == "shutdown_request":
                    content = msg.get("content", "")
                    try:
                        data = json.loads(content)
                        request_id = data.get("request_id", "")
                        BUS.send(name, "lead", json.dumps({"request_id": request_id, "approved": True}), "shutdown_response")
                        member = self._find_member(name)
                        if member:
                            member["status"] = "shutdown"
                            self._save_config()
                        return
                    except:
                        pass
                messages.append({"role": "user", "content": json.dumps(msg)})

            # Call model
            try:
                response = model_with_tools.invoke(
                    [SystemMessage(content=identity_block)] +
                    [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m.get("content", ""))
                     for m in messages]
                )
            except Exception as e:
                print(f"[{name}] Error: {e}")
                break

            messages.append({"role": "assistant", "content": response.content})

            # Check for tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Execute tools
                results = []
                for tc in response.tool_calls:
                    output = self._exec(name, tc["name"], tc.get("args", {}))
                    print(f"  [{name}] {tc['name']}: {str(output)[:120]}")
                    results.append({"type": "tool_result", "tool_call_id": tc.get("id", ""), "content": str(output)})
                messages.append({"role": "user", "content": results})
                idle_start = None  # Reset idle timer
            else:
                # No tool calls - enter idle state
                if idle_start is None:
                    idle_start = time.time()
                else:
                    elapsed = time.time() - idle_start
                    if elapsed > IDLE_TIMEOUT:
                        print(f"[{name}] Idle timeout, shutting down")
                        member = self._find_member(name)
                        if member:
                            member["status"] = "idle"
                            self._save_config()
                        return

                    # Try to find unclaimed work
                    if elapsed >= POLL_INTERVAL:
                        unclaimed = TASKS.find_unclaimed()
                        if unclaimed:
                            task = unclaimed[0]
                            try:
                                TASKS.claim(task["id"], name)
                                print(f"[{name}] Claimed task #{task['id']}: {task['subject']}")
                                messages.append({
                                    "role": "user",
                                    "content": f"You claimed task #{task['id']}: {task['subject']}. Continue working."
                                })
                                idle_start = None  # Reset idle
                            except ValueError:
                                pass

        member = self._find_member(name)
        if member and member["status"] != "shutdown":
            member["status"] = "idle"
            self._save_config()

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        if tool_name == "bash": return _run_bash(args["command"])
        if tool_name == "read_file": return _run_read(args["path"])
        if tool_name == "write_file": return _run_write(args["path"], args["content"])
        if tool_name == "edit_file": return _run_edit(args["path"], args["old_text"], args["new_text"])
        if tool_name == "send_message": return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        if tool_name == "read_inbox": return json.dumps(BUS.read_inbox(sender), indent=2)
        return f"Unknown tool: {tool_name}"

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)


TEAM = TeammateManager(TEAM_DIR)


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
        return (r.stdout + r.stderr).strip()[:50000] or "(no output)"
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
    messages: Annotated[list, add_messages]


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
def spawn_autonomous(name: str, role: str, prompt: str) -> str:
    """Spawn an autonomous teammate that finds work when idle."""
    return TEAM.spawn(name, role, prompt)

@tool
def list_teammates() -> str:
    """List all teammates."""
    return TEAM.list_all()

@tool
def task_create(subject: str, description: str = "") -> str:
    """Create a new task."""
    return json.dumps(TASKS.create(subject, description), indent=2)

@tool
def task_list() -> str:
    """List all tasks."""
    tasks = TASKS.list_all()
    if not tasks:
        return "No tasks."
    lines = []
    for t in tasks:
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
        owner = f" owner={t['owner']}" if t.get("owner") else ""
        lines.append(f"{marker} #{t['id']}: {t['subject']}{owner}")
    return "\n".join(lines)


# Define tool list and tool node
agent_tools = [bash_tool, read_file, write_file, edit_file, spawn_autonomous, list_teammates, task_create, task_list]
tool_node = ToolNode(agent_tools, handle_tool_errors=True)
model_with_tools = model.bind_tools(agent_tools)


# ========== Graph Nodes ==========

SYSTEM_PROMPT = f"""You are a team lead at {WORKDIR}. Teammates are autonomous -- they find work themselves.

Available operations:
- spawn_autonomous(name, role, prompt): Create autonomous teammate
- list_teammates(): Show team status
- task_create(subject, description): Create tasks for teammates to claim
- task_list(): Show all tasks

Autonomous teammates poll for unclaimed work when idle.
"""


def call_model(state: AgentState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    inbox = BUS.read_inbox("lead")
    if inbox:
        messages.append(HumanMessage(content=f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"))
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_edge(START, "agent")
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})

graph = workflow.compile()


def run_agent(query: str):
    initial_state = {"messages": [HumanMessage(content=query)]}
    for event in graph.stream(initial_state):
        node_name = list(event.keys())[0]
        if node_name == "agent":
            response = event[node_name]["messages"][-1]
            if hasattr(response, 'content') and response.content:
                print(f"\nAssistant: {response.content}")


if __name__ == "__main__":
    print("Autonomous Agents (phase18)")
    print("Teammates auto-claim tasks when idle")
    print("Type 'exit' or 'q' to quit\n")

    while True:
        try:
            query = input("\033[36mphase18 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        if query.strip() == "/team":
            print(TEAM.list_all())
            continue
        run_agent(query)