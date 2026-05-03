# Team 协作架构 - Inbox 消息机制

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 为什么需要 Inbox？

传统 Agent 间通信通常是直接调用，但这种方式的问题是：
- 紧耦合
- 难以追踪
- 不支持异步

Inbox 机制提供了：
- **异步通信** - 发送方不阻塞
- **消息持久化** - 消息不会丢失
- **追踪能力** - 可以查看消息历史

---

## 2. Inbox 设计

```python
class Inbox:
    """消息收件箱"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._messages: list[InboxMessage] = []
        self._lock = asyncio.Lock()

    async def send(
        self,
        to_agent: str,
        msg_type: str,
        content: str,
        task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> InboxMessage:
        """发送消息"""

    async def receive(self, mark_read: bool = True) -> Optional[InboxMessage]:
        """接收下一条未读消息"""

    async def receive_all(self, mark_read: bool = True) -> list[InboxMessage]:
        """接收所有未读消息"""

    async def clear(self) -> None:
        """清空消息"""

    def count_unread(self) -> int:
        """统计未读消息数"""
```

---

## 3. 消息类型

```python
@dataclass
class InboxMessage:
    """收件箱消息"""
    id: str                     # 消息唯一标识
    from_agent: Optional[str]   # 发送方
    to_agent: str               # 接收方
    type: str                   # 消息类型
    content: str                # 消息内容
    task_id: Optional[str]      # 关联任务 ID
    metadata: dict              # 额外元数据
    created_at: float           # 创建时间
    read: bool                  # 是否已读
```

**消息类型**

| 类型 | 说明 | 使用场景 |
|------|------|----------|
| `task` | 任务消息 | 分配新任务给 Worker |
| `result` | 结果消息 | Worker 报告执行结果 |
| `control` | 控制消息 | 停止、重启等控制指令 |
| `heartbeat` | 心跳消息 | Worker 存活确认 |

---

## 4. 消息流

```
Lead Agent                TeamManager                Worker
    │                         │                        │
    │──── assign_task() ────► │                        │
    │                         │──── 任务消息 ────────► │
    │                         │                        │
    │                         │ ◄─── 结果消息 ────────│
    │                         │                        │
    │◄─── 回调(result) ──────│                        │
    │                         │                        │
```

---

## 5. Worker Agent 使用 Inbox

```python
class WorkerAgent:
    def __init__(self, inbox: Inbox, team_manager: TeamManager):
        self.inbox = inbox
        self.team = team_manager

    async def run(self) -> None:
        while True:
            # 1. 检查消息
            message = await self.inbox.receive()
            if message:
                # 2. 执行任务
                result = await self.execute(message)

                # 3. 报告结果
                await self.team.on_task_completed(message.task_id, result)
```

---

## 6. 并行关键点

> **并行关键**：
> - `asyncio.gather()` 让所有 Worker 同时开始执行
> - **工具必须使用 `asyncio.create_subprocess_*` 实现真正异步 I/O**
> - 纯 Python CPU 任务受 GIL 限制无法通过 to_thread 并行，需用 multiprocessing
> - `to_thread` 仅适合：调用同步 I/O 库 或 会释放 GIL 的 C 扩展

---

## 7. 相关文档

- [manager.md](manager.md) - TeamManager 实现
- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构