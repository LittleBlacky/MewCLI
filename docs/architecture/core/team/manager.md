# Team 协作架构 - TeamManager

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Team Manager 职责

TeamManager 是团队协作的核心，负责：

1. **Worker 管理** - 创建、销毁、监控 Worker
2. **任务分配** - 将任务分配给可用的 Worker
3. **状态追踪** - 追踪 Worker 和任务状态
4. **结果汇总** - 收集 Worker 结果并通知 Lead Agent
5. **负载均衡** - 平衡 Worker 负载

---

## 2. Team Manager 架构

```
TeamManager
    │
    ├── Worker Pool
    │   ├── WorkerInfo (worker_1)
    │   ├── WorkerInfo (worker_2)
    │   └── WorkerInfo (worker_N)
    │
    ├── Inbox Map
    │   ├── agent_1 -> Inbox
    │   ├── agent_2 -> Inbox
    │   └── worker_1 -> Inbox
    │
    ├── Task Queue (优先级队列)
    │   ├── Task (priority=1)
    │   ├── Task (priority=2)
    │   └── Task (priority=3)
    │
    ├── 任务分配器
    │   ├── 查找可用 Worker
    │   ├── 分配任务
    │   └── 更新状态
    │
    └── 回调管理器
        └── task_id -> callback
```

---

## 3. TeamManager 核心方法

```python
class TeamManager:
    """团队管理器"""

    def __init__(self, config: TeamConfig):
        self.config = config
        self._workers: dict[str, WorkerInfo] = {}
        self._inboxes: dict[str, Inbox] = {}
        self._task_queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._task_callbacks: dict[str, Callable] = {}

    async def create_worker(self, config: AgentConfig) -> WorkerInfo:
        """创建新 Worker"""

    async def destroy_worker(self, worker_id: str) -> bool:
        """销毁 Worker"""

    async def assign_task(
        self,
        task: Task,
        callback: Optional[Callable] = None
    ) -> str:
        """分配任务给 Worker"""

    async def on_task_completed(self, task_id: str, result: TaskResult) -> None:
        """处理任务完成"""

    async def on_task_failed(self, task_id: str, error: str) -> None:
        """处理任务失败"""

    async def get_stats(self) -> dict:
        """获取团队统计信息"""

    async def shutdown(self) -> None:
        """关闭所有 Worker"""
```

---

## 4. Worker 管理

### 4.1 WorkerInfo 定义

```python
@dataclass
class WorkerInfo:
    """Worker 信息"""
    id: str                     # Worker 唯一标识
    name: str                   # Worker 名称
    status: WorkerStatus        # 状态：IDLE / BUSY / STOPPED
    current_task_id: Optional[str]  # 当前任务 ID
    tasks_completed: int        # 已完成任务数
    tasks_failed: int           # 失败任务数
    created_at: float           # 创建时间
    last_heartbeat: float       # 最后心跳时间
    metadata: dict              # 额外元数据
```

### 4.2 Worker 状态机

```
                    create_worker()
                         │
                         ▼
                      IDLE
         ┌──────────────┼──────────────┐
         │              │              │
    assign_task()  idle_timeout   destroy_worker()
         │              │              │
         ▼              ▼              ▼
       BUSY         STOPPED          STOPPED
         │              ▲
         │              │
    task_complete()    │
         │              │
         └──────────────┘
```

### 4.3 心跳机制

```python
class WorkerInfo:
    def is_alive(self, timeout: float = 60.0) -> bool:
        """检查 Worker 是否存活"""
        return datetime.now().timestamp() - self.last_heartbeat < timeout

    def update_heartbeat(self) -> None:
        """更新心跳时间戳"""
        self.last_heartbeat = datetime.now().timestamp()
```

**为什么需要心跳机制？**

Worker 可能因为以下原因变得不可用：
- 进程崩溃
- 网络问题
- 长时间执行
- 死锁

心跳机制让 TeamManager 能够检测不响应的 Worker，并采取相应措施（如重新分配任务）。

---

## 5. 任务分配策略

### 5.1 分配算法

```python
async def _find_available_worker(self) -> Optional[WorkerInfo]:
    """查找可用的 Worker"""
    for worker in self._workers.values():
        if worker.status == WorkerStatus.IDLE and worker.is_alive():
            return worker
    return None
```

### 5.2 分配流程

```
                    assign_task(task)
                         │
                         ▼
              ┌────────────────────────┐
              │  查找可用 Worker       │
              └───────────┬────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
        有可用 Worker            无可用 Worker
              │                       │
              ▼                       ▼
    ┌─────────────────┐      ┌─────────────────┐
    │  分配任务       │      │  加入任务队列   │
    │  更新状态      │      │  返回空字符串   │
    └────────┬────────┘      └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  发送消息到     │
    │  Worker Inbox   │
    └─────────────────┘
```

### 5.3 任务队列

当没有可用 Worker 时，任务进入队列：

```python
_task_queue: asyncio.PriorityQueue[Task]

async def _process_queue(self) -> None:
    """处理等待队列中的任务"""
    while not self._task_queue.empty():
        worker = await self._find_available_worker()
        if not worker:
            break

        task = self._task_queue.get_nowait()
        await self.assign_task(task)
```

---

## 6. 结果处理

### 6.1 完成回调

```python
async def on_task_completed(self, task_id: str, result: TaskResult) -> None:
    """处理任务完成"""
    # 1. 更新 Worker 状态
    for worker in self._workers.values():
        if worker.current_task_id == task_id:
            worker.status = WorkerStatus.IDLE
            worker.current_task_id = None
            worker.tasks_completed += 1
            break

    # 2. 通知回调
    if task_id in self._task_callbacks:
        callback = self._task_callbacks.pop(task_id)
        await callback(result)

    # 3. 处理队列中的任务
    await self._process_queue()
```

### 6.2 失败处理

```python
async def on_task_failed(self, task_id: str, error: str) -> None:
    """处理任务失败"""
    # 1. 更新 Worker 状态
    for worker in self._workers.values():
        if worker.current_task_id == task_id:
            worker.status = WorkerStatus.IDLE
            worker.current_task_id = None
            worker.tasks_failed += 1
            break

    # 2. 创建失败结果
    result = TaskResult(
        task_id=task_id,
        success=False,
        error=error,
    )

    # 3. 通知回调
    if task_id in self._task_callbacks:
        callback = self._task_callbacks.pop(task_id)
        await callback(result)
```

---

## 7. Team 配置

```python
@dataclass
class TeamConfig:
    """团队配置"""
    max_workers: Optional[int] = None  # 最大 Worker 数，None=无限制
    task_timeout: float = 60.0         # 任务超时时间（秒）
    worker_idle_timeout: float = 300.0 # Worker 空闲超时（秒）
    auto_shutdown_idle: bool = True     # 自动关闭空闲 Worker
```

---

## 8. 完整任务流程数据流

```
用户输入
    │
    ▼
Lead Agent 理解任务
    │
    ▼
Lead Agent 分解任务
    │
    ▼
┌───────────────────────────────────────┐
│            TeamManager                │
│  ┌─────────────────────────────────┐  │
│  │         Worker Pool            │  │
│  │  [W1] [W2] [W3] [W4] ...       │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │         Task Queue             │  │
│  │  [T1] [T2] [T3] ...            │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
    │
    ▼
TeamManager 分配任务
    │
    ├──► Worker 1 执行子任务 1
    ├──► Worker 2 执行子任务 2
    ├──► Worker 3 执行子任务 3
    └──► Worker 4 执行子任务 4
    │
    ▼
Worker 报告结果
    │
    ▼
TeamManager 汇总结果
    │
    ▼
Lead Agent 生成最终回复
    │
    ▼
用户输出
```

---

## 9. 相关文档

- [inbox.md](inbox.md) - Inbox 消息机制
- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构