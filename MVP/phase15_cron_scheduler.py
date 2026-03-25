#!/usr/bin/env python3
"""
phase15_cron_scheduler.py - Cron / Scheduled Tasks

The agent can schedule prompts for future execution using standard cron
expressions. When a schedule matches the current time, it pushes a
notification back into the main conversation loop.

Cron expression: 5 fields
+-------+-------+-------+-------+-------+
| min   | hour  | dom   | month | dow   |
| 0-59  | 0-23  | 1-31  | 1-12  | 0-6   |
+-------+-------+-------+-------+-------+

Two persistence modes:
- session-only: In-memory list, lost on exit
- durable: Persists to .claude/scheduled_tasks.json

Two trigger modes:
- recurring: Repeats until deleted or 7-day auto-expiry
- one-shot: Fires once, then auto-deleted
"""
import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
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
SCHEDULED_TASKS_FILE = WORKDIR / ".claude" / "scheduled_tasks.json"
CRON_LOCK_FILE = WORKDIR / ".claude" / "cron.lock"
AUTO_EXPIRY_DAYS = 7
JITTER_MINUTES = [0, 30]
JITTER_OFFSET_MAX = 4

model = init_chat_model(
    MODEL_ID,
    model_provider=PROVIDER,
    temperature=0,
    max_tokens=8000,
    base_url=BASE_URL,
    api_key=API_KEY,
)


class CronLock:
    """PID-file-based lock to prevent multiple sessions from firing the same cron job."""

    def __init__(self, lock_path: Path = None):
        self._lock_path = lock_path or CRON_LOCK_FILE

    def acquire(self) -> bool:
        if self._lock_path.exists():
            try:
                stored_pid = int(self._lock_path.read_text().strip())
                os.kill(stored_pid, 0)
                return False
            except (ValueError, ProcessLookupError, PermissionError, OSError):
                pass
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.write_text(str(os.getpid()))
        return True

    def release(self):
        """Remove the lock file if it belongs to this process."""
        try:
            if self._lock_path.exists():
                stored_pid = int(self._lock_path.read_text().strip())
                if stored_pid == os.getpid():
                    self._lock_path.unlink()
        except (ValueError, OSError):
            pass


def cron_matches(expr: str, dt: datetime) -> bool:
    """Check if a 5-field cron expression matches a given datetime."""
    fields = expr.strip().split()
    if len(fields) != 5:
        return False
    values = [dt.minute, dt.hour, dt.day, dt.month, dt.weekday()]
    cron_dow = (dt.weekday() + 1) % 7
    values[4] = cron_dow
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    for field, value, (lo, hi) in zip(fields, values, ranges):
        if not _field_matches(field, value, lo, hi):
            return False
    return True


def _field_matches(field: str, value: int, lo: int, hi: int) -> bool:
    """Match a single cron field against a value."""
    if field == "*":
        return True
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)
        if part == "*":
            if (value - lo) % step == 0:
                return True
        elif "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            if start <= value <= end and (value - start) % step == 0:
                return True
        else:
            if int(part) == value:
                return True
    return False


class CronScheduler:
    """Manage scheduled tasks with background checking."""

    def __init__(self):
        self.tasks = []
        self.queue = Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._last_check_minute = -1

    def start(self):
        """Load durable tasks and start the background check thread."""
        self._load_durable()
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        count = len(self.tasks)
        if count:
            print(f"[Cron] Loaded {count} scheduled tasks")

    def stop(self):
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def create(
        self, cron_expr: str, prompt: str, recurring: bool = True, durable: bool = False
    ) -> str:
        """Create a new scheduled task. Returns the task ID."""
        task_id = str(uuid.uuid4())[:8]
        now = time.time()
        task = {
            "id": task_id,
            "cron": cron_expr,
            "prompt": prompt,
            "recurring": recurring,
            "durable": durable,
            "createdAt": now,
        }
        if recurring:
            task["jitter_offset"] = self._compute_jitter(cron_expr)
        self.tasks.append(task)
        if durable:
            self._save_durable()
        mode = "recurring" if recurring else "one-shot"
        store = "durable" if durable else "session-only"
        return f"Created task {task_id} ({mode}, {store}): cron={cron_expr}"

    def delete(self, task_id: str) -> str:
        """Delete a scheduled task by ID."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if len(self.tasks) < before:
            self._save_durable()
            return f"Deleted task {task_id}"
        return f"Task {task_id} not found"

    def list_tasks(self) -> str:
        """List all scheduled tasks."""
        if not self.tasks:
            return "No scheduled tasks."
        lines = []
        for t in self.tasks:
            mode = "recurring" if t["recurring"] else "one-shot"
            store = "durable" if t["durable"] else "session"
            age_hours = (time.time() - t["createdAt"]) / 3600
            lines.append(
                f"  {t['id']}  {t['cron']}  [{mode}/{store}] "
                f"({age_hours:.1f}h old): {t['prompt'][:60]}"
            )
        return "\n".join(lines)

    def drain_notifications(self) -> list[str]:
        """Drain all pending notifications from the queue."""
        notifications = []
        while True:
            try:
                notifications.append(self.queue.get_nowait())
            except Empty:
                break
        return notifications

    def _compute_jitter(self, cron_expr: str) -> int:
        """If cron targets :00 or :30, return a small offset (1-4 minutes)."""
        fields = cron_expr.strip().split()
        if len(fields) < 1:
            return 0
        minute_field = fields[0]
        try:
            minute_val = int(minute_field)
            if minute_val in JITTER_MINUTES:
                return (hash(cron_expr) % JITTER_OFFSET_MAX) + 1
        except ValueError:
            pass
        return 0

    def _check_loop(self):
        """Background thread: check every second if any task is due."""
        while not self._stop_event.is_set():
            now = datetime.now()
            current_minute = now.hour * 60 + now.minute
            if current_minute != self._last_check_minute:
                self._last_check_minute = current_minute
                self._check_tasks(now)
            self._stop_event.wait(timeout=1)

    def _check_tasks(self, now: datetime):
        """Check all tasks against current time, fire matches."""
        expired = []
        fired_oneshots = []
        for task in self.tasks:
            age_days = (time.time() - task["createdAt"]) / 86400
            if task["recurring"] and age_days > AUTO_EXPIRY_DAYS:
                expired.append(task["id"])
                continue
            check_time = now
            jitter = task.get("jitter_offset", 0)
            if jitter:
                check_time = now - timedelta(minutes=jitter)
            if cron_matches(task["cron"], check_time):
                notification = f"[Scheduled task {task['id']}]: {task['prompt']}"
                self.queue.put(notification)
                task["last_fired"] = time.time()
                print(f"[Cron] Fired: {task['id']}")
                if not task["recurring"]:
                    fired_oneshots.append(task["id"])
        if expired or fired_oneshots:
            remove_ids = set(expired) | set(fired_oneshots)
            self.tasks = [t for t in self.tasks if t["id"] not in remove_ids]
            for tid in expired:
                print(f"[Cron] Auto-expired: {tid}")
            for tid in fired_oneshots:
                print(f"[Cron] One-shot completed and removed: {tid}")
            self._save_durable()

    def _load_durable(self):
        """Load durable tasks from .claude/scheduled_tasks.json."""
        if not SCHEDULED_TASKS_FILE.exists():
            return
        try:
            data = json.loads(SCHEDULED_TASKS_FILE.read_text())
            self.tasks = [t for t in data if t.get("durable")]
        except Exception as e:
            print(f"[Cron] Error loading tasks: {e}")

    def _save_durable(self):
        """Save durable tasks to disk."""
        durable = [t for t in self.tasks if t.get("durable")]
        SCHEDULED_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULED_TASKS_FILE.write_text(json.dumps(durable, indent=2) + "\n")


scheduler = CronScheduler()


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


@tool
def cron_create(
    cron: str,
    prompt: str,
    recurring: bool = True,
    durable: bool = False,
) -> str:
    """Schedule a recurring or one-shot task with a cron expression."""
    return scheduler.create(cron, prompt, recurring, durable)


@tool
def cron_delete(id: str) -> str:
    """Delete a scheduled task by ID."""
    return scheduler.delete(id)


@tool
def cron_list() -> str:
    """List all scheduled tasks."""
    return scheduler.list_tasks()


ALL_TOOLS = [bash, read_file, write_file, edit_file, cron_create, cron_delete, cron_list]
tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=True)
model_with_tools = model.bind_tools(ALL_TOOLS)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


SYSTEM = (
    f"You are a coding agent at {WORKDIR}. Use tools to solve tasks.\n\n"
    "You can schedule future work with cron_create. Tasks fire automatically "
    "and their prompts are injected into the conversation."
)


def call_model(state: AgentState) -> dict:
    """Stream model responses with notification injection."""
    messages_with_system = [SystemMessage(content=SYSTEM)] + state["messages"]

    notifications = scheduler.drain_notifications()
    for note in notifications:
        print(f"[Cron notification] {note[:100]}")
        messages_with_system.append(HumanMessage(content=note))

    response = model_with_tools.invoke(messages_with_system)
    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Decide whether to continue tool execution or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

graph = workflow.compile()


if __name__ == "__main__":
    scheduler.start()
    print("[Cron scheduler running. Background checks every second.]")
    state: AgentState = {"messages": []}

    try:
        while True:
            try:
                q = input("\033[36mphase15 >> \033[0m")
            except (EOFError, KeyboardInterrupt):
                break
            if q.strip().lower() in ("q", "exit", ""):
                break
            if q.strip() == "/cron":
                print(scheduler.list_tasks())
                continue

            state["messages"].append(HumanMessage(content=q))
            state = graph.invoke(state)
            print()
    finally:
        scheduler.stop()
