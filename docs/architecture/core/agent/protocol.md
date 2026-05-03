# Agent 核心架构 - 通信协议

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Agent 间通信架构

Agent 间通过 Team Manager 进行通信：

```
Lead Agent <────> Team Manager <────> Worker Agents
                    │
                    ├── 任务分配 (assign_task)
                    ├── 结果上报 (on_task_completed)
                    └── 状态查询 (get_stats)
```

---

## 2. 资源隔离规则

**混合隔离方案**：上下文隔离，Memory/Skill/Tool 共享

| 资源        | Lead Agent          | Worker Agent   | 说明                          |
| ----------- | ------------------- | -------------- | ----------------------------- |
| **Context** | 完整 SessionContext | SubtaskContext | Worker 间上下文隔离           |
| **Memory**  | 读写                | 只读           | Lead 可创建/更新，Worker 检索 |
| **Skill**   | 读写                | 只读           | Lead 可创建/更新，Worker 使用 |
| **Tool**    | 全部工具            | 全部工具       | 共享                          |

**设计理由**：

- **Context 隔离**：防止 Worker 之间互相干扰，每个 Worker 独立处理子任务
- **Memory 共享**：项目知识应该对所有 Agent 可见，避免重复读取
- **Skill 共享**：技能是通用的，所有 Agent 都可以使用
- **Tool 共享**：工具能力一致，便于统一管理

---

## 3. 消息格式

### 3.1 InboxMessage

```python
@dataclass
class InboxMessage:
    """收件箱消息"""
    id: str                          # 消息唯一标识
    sender_id: str                   # 发送者 ID
    receiver_id: str                 # 接收者 ID
    message_type: MessageType        # 消息类型
    payload: dict                    # 消息内容
    timestamp: float                # 创建时间
    status: MessageStatus           # 消息状态
```

### 3.2 消息类型

```python
class MessageType(Enum):
    """消息类型枚举"""
    TASK = "task"           # 任务消息
    RESULT = "result"       # 结果消息
    CONTROL = "control"     # 控制消息
    HEARTBEAT = "heartbeat" # 心跳消息


class MessageStatus(Enum):
    """消息状态枚举"""
    PENDING = "pending"     # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"       # 失败
```

### 3.3 消息类型详解

消息类型是 Agent 间通信的"信封类型"，让不同角色知道如何处理消息：

| 类型 | 发送方 → 接收方 | 用途 | payload 示例 |
|------|----------------|------|-------------|
| **TASK** | Lead → Worker | 分配子任务 | `{task_id, description, context}` |
| **RESULT** | Worker → Lead | 返回执行结果 | `{task_id, output, success}` |
| **CONTROL** | Lead/Team → Worker | 控制命令 | `{action: "cancel"/"pause"/"resume"}` |
| **HEARTBEAT** | Worker → Lead/Team | 心跳保活 | `{worker_id, status: "healthy"}` |

**通信流程图**：

```
Lead Agent                    Team Manager                   Worker 1, 2, 3
    │                              │                              │
    ├─── TASK ───────────────────► │                              │
    │                              ├─── TASK ───────────────────► │
    │                              │                              │
    │                              │◄──── RESULT ─────────────── │
    │◄──── RESULT ─────────────── │                              │
    │                              │                              │
    ├─── CONTROL (cancel) ───────► │                              │
    │                              ├─── CONTROL ────────────────► │ (某个 Worker)
    │                              │                              │
    │                              │◄──── HEARTBEAT ─────────── │
    │◄──── HEARTBEAT ───────────── │ (每 30s 上报一次存活状态)      │
```

**简单说明**：

| 类型 | 含义 |
|------|------|
| **TASK** | 有活儿干 |
| **RESULT** | 活儿干完了 |
| **CONTROL** | 让你停/继续 |
| **HEARTBEAT** | 我还活着 |

---

## 4. 协议定义

### 4.1 Lead → Team Manager

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| assign_task(task) | 分配任务 | Task | worker_id |
| cancel_task(task_id) | 取消任务 | task_id | bool |
| get_task_status(task_id) | 查询状态 | task_id | TaskStatus |

### 4.2 Worker → Team Manager

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| on_task_completed(task_id, result) | 上报结果 | task_id, TaskResult | bool |
| on_task_failed(task_id, error) | 上报失败 | task_id, error | bool |
| send_heartbeat() | 发送心跳 | - | bool |

### 4.3 Team Manager → Worker

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| dispatch(task) | 分发任务 | Task | bool |
| cancel(task_id) | 取消任务 | task_id | bool |
| ping() | 健康检查 | - | bool |

---

## 5. 协议实现示例

### 5.1 Lead 分配任务

```python
# Lead Agent
async def assign(self, task: Task) -> str:
    """分配任务给 Worker"""
    worker_id = await self.team_manager.assign_task(task)
    task.assigned_to = worker_id
    return worker_id
```

### 5.2 Worker 报告结果

```python
# Worker Agent
async def report_result(self, task_id: str, result: TaskResult) -> None:
    """报告任务结果"""
    await self.team_manager.on_task_completed(task_id, result)

async def report_failure(self, task_id: str, error: str) -> None:
    """报告任务失败"""
    await self.team_manager.on_task_failed(task_id, error)
```

---

## 6. 相关文档

- [lead.md](lead.md) - Lead Agent 实现
- [worker.md](worker.md) - Worker Agent 实现
- [../team/index.md](../team/index.md) - Team 协作架构