"""Autonomous agent module - Idle cycle with task polling."""
import asyncio
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class IdleConfig:
    """Configuration for autonomous agent."""
    poll_interval: int = 5  # seconds
    idle_timeout: int = 60  # seconds
    max_idle_cycles: int = 12


class AutonomousAgent:
    """Autonomous agent with idle cycle.

    Lifecycle:
    1. Spawn -> WORK
    2. WORK -> IDLE (on stop_reason != tool_use)
    3. IDLE -> check inbox, scan tasks, claim work
    4. IDLE -> timeout -> shutdown

    Key insight: "An idle teammate can safely claim ready work
    instead of waiting for every assignment from the lead."
    """

    def __init__(
        self,
        name: str,
        role: str,
        task: str,
        poll_interval: int = 5,
        idle_timeout: int = 60,
    ):
        self.name = name
        self.role = role
        self.task = task
        self.poll_interval = poll_interval
        self.idle_timeout = idle_timeout

        self.running = True
        self.idle = False
        self.idle_cycles = 0
        self.last_activity = time.time()
        self.inbox: list[dict] = []

    async def work(self, agent_runner) -> str:
        """Execute the main task."""
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content=self.task)]
        result = await agent_runner.run(messages)
        return str(result.get("messages", []))

    def check_inbox(self) -> Optional[dict]:
        """Check for new messages."""
        if self.inbox:
            return self.inbox.pop(0)
        return None

    def scan_tasks(self) -> Optional[dict]:
        """Scan for unclaimed tasks."""
        from pathlib import Path

        storage_dir = Path.cwd() / ".mini-agent-cli" / "tasks"
        if not storage_dir.exists():
            return None

        for task_file in storage_dir.glob("task_*.json"):
            try:
                import json
                task = json.loads(task_file.read_text())

                # Claim unclaimed task
                if task.get("status") == "pending" and not task.get("owner"):
                    task["owner"] = self.name
                    task_file.write_text(json.dumps(task, indent=2))
                    return task
            except Exception:
                continue

        return None

    async def idle_cycle(self, agent_runner) -> None:
        """Run idle cycle with polling."""
        self.idle = True
        start_time = time.time()

        while self.running and self.idle_cycles < IdleConfig().max_idle_cycles:
            elapsed = time.time() - start_time
            if elapsed > self.idle_timeout:
                break

            # Check inbox
            msg = self.check_inbox()
            if msg:
                self.idle = False
                self.idle_cycles = 0
                # Resume work with message
                self.task = f"Resume task: {msg.get('content', '')}"
                return

            # Scan tasks
            task = self.scan_tasks()
            if task:
                self.idle = False
                self.idle_cycles = 0
                self.task = f"Execute task: {task.get('subject', '')}"
                return

            # Sleep before next poll
            await asyncio.sleep(self.poll_interval)
            self.idle_cycles += 1

        # Timeout reached
        if self.idle_cycles >= IdleConfig().max_idle_cycles:
            self.running = False

    def receive_message(self, message: dict) -> None:
        """Receive a message from teammate."""
        self.inbox.append(message)
        if self.idle:
            self.idle = False
            self.idle_cycles = 0

    def stop(self) -> None:
        """Stop the autonomous agent."""
        self.running = False

    async def run(self, agent_runner) -> str:
        """Run the autonomous agent lifecycle."""
        while self.running:
            if self.idle:
                await self.idle_cycle(agent_runner)
            else:
                result = await self.work(agent_runner)
                self.last_activity = time.time()

                # Check if should go idle
                # (In real implementation, this would check stop_reason)
                self.idle = True

        return f"Agent {self.name} completed"


class TeammateManager:
    """Manages multiple autonomous teammates."""

    def __init__(self):
        self.teammates: dict[str, AutonomousAgent] = {}

    def spawn(
        self,
        name: str,
        role: str,
        task: str,
        poll_interval: int = 5,
        idle_timeout: int = 60,
    ) -> AutonomousAgent:
        """Spawn a new teammate."""
        agent = AutonomousAgent(name, role, task, poll_interval, idle_timeout)
        self.teammates[name] = agent
        return agent

    def get(self, name: str) -> Optional[AutonomousAgent]:
        """Get teammate by name."""
        return self.teammates.get(name)

    def list_teammates(self) -> list[dict]:
        """List all teammates."""
        return [
            {
                "name": agent.name,
                "role": agent.role,
                "idle": agent.idle,
                "running": agent.running,
            }
            for agent in self.teammates.values()
        ]

    def send_message(self, target: str, message: dict) -> bool:
        """Send message to teammate."""
        agent = self.teammates.get(target)
        if agent:
            agent.receive_message(message)
            return True
        return False

    def stop_all(self) -> None:
        """Stop all teammates."""
        for agent in self.teammates.values():
            agent.stop()
        self.teammates.clear()


__all__ = ["AutonomousAgent", "TeammateManager", "IdleConfig"]
