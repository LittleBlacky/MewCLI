"""Team manager - manages multi-agent collaboration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Awaitable

from .inbox import Inbox, InboxMessage, WorkerInfo, WorkerStatus
from ..agent import Task, TaskStatus, TaskResult, AgentConfig, AgentRole


@dataclass
class TeamConfig:
    """Team configuration."""

    max_workers: Optional[int] = None  # None = unlimited
    task_timeout: float = 60.0  # Task timeout in seconds
    worker_idle_timeout: float = 300.0  # Worker idle timeout (5 min)
    auto_shutdown_idle: bool = True  # Auto shutdown idle workers


class TeamManager:
    """Manages multi-agent collaboration.

    Responsibilities:
    - Create/destroy workers
    - Assign tasks to workers
    - Track worker status
    - Aggregate results
    """

    def __init__(self, config: Optional[TeamConfig] = None):
        self.config = config or TeamConfig()
        self._workers: dict[str, WorkerInfo] = {}
        self._inboxes: dict[str, Inbox] = {}
        self._task_queue: asyncio.Queue[Task] = asyncio.Queue()
        self._task_callbacks: dict[str, Callable[[TaskResult], Awaitable[None]]] = {}
        self._lock = asyncio.Lock()
        self._worker_counter = 0

    @property
    def workers(self) -> dict[str, WorkerInfo]:
        """Get all workers."""
        return self._workers.copy()

    @property
    def worker_count(self) -> int:
        """Get worker count."""
        return len(self._workers)

    def get_inbox(self, agent_id: str) -> Inbox:
        """Get or create inbox for agent."""
        if agent_id not in self._inboxes:
            self._inboxes[agent_id] = Inbox(agent_id)
        return self._inboxes[agent_id]

    async def create_worker(self, config: AgentConfig) -> WorkerInfo:
        """Create a new worker."""
        async with self._lock:
            self._worker_counter += 1
            worker_id = f"worker_{self._worker_counter}"
            worker = WorkerInfo(
                id=worker_id,
                name=config.name,
                status=WorkerStatus.IDLE,
                metadata={
                    "tools": config.tools,
                    "capabilities": config.capabilities,
                },
            )
            self._workers[worker_id] = worker
            self._inboxes[worker_id] = Inbox(worker_id)
            return worker

    async def destroy_worker(self, worker_id: str) -> bool:
        """Destroy a worker."""
        async with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                if worker_id in self._inboxes:
                    del self._inboxes[worker_id]
                return True
            return False

    async def assign_task(
        self,
        task: Task,
        callback: Optional[Callable[[TaskResult], Awaitable[None]]] = None,
    ) -> str:
        """Assign a task to an available worker.

        Returns worker_id that received the task.
        """
        # Find available worker
        worker = await self._find_available_worker()
        if not worker:
            # No available worker, add to queue
            await self._task_queue.put(task)
            return ""

        # Assign task to worker
        async with self._lock:
            worker.status = WorkerStatus.BUSY
            worker.current_task_id = task.id

        task.assigned_to = worker.id
        task.status = TaskStatus.PENDING

        # Send task to worker inbox
        inbox = self.get_inbox(worker.id)
        await inbox.send(
            to_agent=worker.id,
            msg_type="task",
            content=task.description,
            task_id=task.id,
        )

        if callback:
            self._task_callbacks[task.id] = callback

        return worker.id

    async def _find_available_worker(self) -> Optional[WorkerInfo]:
        """Find an available worker."""
        for worker in self._workers.values():
            if worker.status == WorkerStatus.IDLE and worker.is_alive():
                return worker
        return None

    async def on_task_completed(self, task_id: str, result: TaskResult) -> None:
        """Handle task completion."""
        # Find worker and update status
        for worker in self._workers.values():
            if worker.current_task_id == task_id:
                async with self._lock:
                    worker.status = WorkerStatus.IDLE
                    worker.current_task_id = None
                    worker.tasks_completed += 1
                break

        # Notify callback
        if task_id in self._task_callbacks:
            callback = self._task_callbacks.pop(task_id)
            await callback(result)

        # Process queued tasks
        await self._process_queue()

    async def on_task_failed(self, task_id: str, error: str) -> None:
        """Handle task failure."""
        # Find worker and update status
        for worker in self._workers.values():
            if worker.current_task_id == task_id:
                async with self._lock:
                    worker.status = WorkerStatus.IDLE
                    worker.current_task_id = None
                    worker.tasks_failed += 1
                break

        # Create failed result
        result = TaskResult(
            task_id=task_id,
            success=False,
            error=error,
        )

        # Notify callback
        if task_id in self._task_callbacks:
            callback = self._task_callbacks.pop(task_id)
            await callback(result)

    async def _process_queue(self) -> None:
        """Process pending tasks in queue."""
        while not self._task_queue.empty():
            worker = await self._find_available_worker()
            if not worker:
                break

            try:
                task = self._task_queue.get_nowait()
                await self.assign_task(task)
            except asyncio.QueueEmpty:
                break

    async def get_stats(self) -> dict:
        """Get team statistics."""
        return {
            "worker_count": len(self._workers),
            "workers": [
                {
                    "id": w.id,
                    "name": w.name,
                    "status": w.status.value,
                    "tasks_completed": w.tasks_completed,
                    "tasks_failed": w.tasks_failed,
                }
                for w in self._workers.values()
            ],
            "queue_size": self._task_queue.qsize(),
        }

    async def shutdown(self) -> None:
        """Shutdown all workers."""
        async with self._lock:
            for worker in self._workers.values():
                worker.status = WorkerStatus.STOPPED
            self._workers.clear()
            self._inboxes.clear()
        self._task_callbacks.clear()