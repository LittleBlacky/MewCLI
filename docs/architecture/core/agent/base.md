# Agent 核心架构 - 基础类型定义

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 角色定义 (AgentRole)

```python
class AgentRole(Enum):
    """Agent 角色枚举"""
    LEAD = "lead"      # Lead Agent：理解、分解、汇总
    WORKER = "worker"  # Worker Agent：执行子任务
```

**为什么需要 LEAD 和 WORKER？**

Lead Agent 负责理解用户意图、分解任务、汇总结果，Worker Agent 负责执行具体任务。这种主从模式是系统的基础协作模式。

---

## 2. 任务定义 (Task)

```python
@dataclass
class Task:
    id: str                          # 任务唯一标识
    description: str                 # 任务描述
    assigned_to: Optional[str]        # 分配的 Agent ID
    status: TaskStatus                # 任务状态
    result: Optional[str]             # 执行结果
    error: Optional[str]              # 错误信息
    parent_id: Optional[str]          # 父任务 ID（用于树形结构）
    children_ids: list[str]           # 子任务 ID 列表
    created_at: float                 # 创建时间
    started_at: Optional[float]      # 开始时间
    completed_at: Optional[float]     # 完成时间
    metadata: dict                   # 额外元数据
```

**为什么 Task 要有 parent_id 和 children_ids？**

Lead Agent 将任务分解为子任务，形成树形结构。这种设计支持：

- 追踪任务层级关系
- 支持子任务并行执行
- 支持结果汇总
- 支持任务依赖分析

---

## 3. Task 状态机

```
                    create()
                        │
                        ▼
                    PENDING ──────► CANCELLED
                        │                ▲
                   start()              │
                        │          cancel()
                        ▼
                     RUNNING
                        │
                   complete() ◄────────┘
                        │
                        ▼
              ┌──────► DONE
              │            ▲
         fail()           complete()
              │            │
              └──────── FAILED
```

---

## 4. 消息定义 (Message)

```python
@dataclass
class Message:
    role: MessageRole       # 消息角色
    content: str            # 消息内容
    tool_calls: Optional[list[dict]]  # 工具调用
    tool_call_id: Optional[str]       # 工具调用 ID
    name: Optional[str]             # 工具名称
    metadata: dict                   # 额外元数据
    created_at: float                # 创建时间
```

**为什么 Message 要支持 to_langchain()？**

MiniCode 使用 LangGraph 作为核心框架，Message 需要转换为 LangChain 的消息格式。这个方法封装了转换逻辑，避免在使用处写转换代码。

---

## 5. Agent 配置 (AgentConfig)

```python
@dataclass
class AgentConfig:
    name: str                    # Agent 标识符
    role: AgentRole              # 角色：LEAD 或 WORKER
    tools: list[str]             # 可用工具名称列表
    capabilities: list[str]      # 特殊能力列表
    model: str = "claude-sonnet-4-7"    # 使用的模型
    temperature: float = 0.0           # LLM temperature
    max_tokens: int = 8000             # 最大输出 tokens
```

---

## 6. 消息类型

```python
class MessageType(Enum):
    """消息类型枚举"""
    TASK = "task"           # 任务消息
    RESULT = "result"       # 结果消息
    CONTROL = "control"     # 控制消息
    HEARTBEAT = "heartbeat" # 心跳消息
```

**消息类型详解**：

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

## 7. 任务分解类型

```python
from pydantic import BaseModel, Field
from typing import Optional


class SubTask(BaseModel):
    """子任务定义 - 用于 LLM 结构化输出"""
    description: str = Field(description="子任务描述")
    dependencies: list[str] = Field(default_factory=list, description="依赖的其他子任务 ID")


class DecompositionResult(BaseModel):
    """分解结果 - 用于 LLM 结构化输出"""
    should_decompose: bool = Field(description="是否需要分解")
    reason: str = Field(description="决策理由")
    subtasks: list[SubTask] = Field(default_factory=list, description="子任务列表")
```

## 7. 执行模式

MiniCode 支持两种执行模式，可根据任务类型选择：

| 模式 | 说明 | 适用场景 | 配置方式 |
|------|------|----------|----------|
| **ReAct** | 边做边想，工具调用后立即分析结果 | 简单任务、快速执行 | 默认模式 |
| **Plan-and-Solve** | 先制定完整计划，再按计划执行 | 复杂任务、多步骤协调 | 配置 `mode="plan"` |

**模式差异**：

```
ReAct:
  Task → Think → Action → Observe → Think → Action → Done

Plan-and-Solve:
  Task → Plan → Execute Step 1 → Verify → Execute Step 2 → ... → Done
```

---

## 8. 与 LangGraph 集成

### 8.1 Agent State 与 GraphState 关系

```
GraphState (基础设施层 - infra/graph)
    │
    ├── messages: list           # 基础消息列表
    ├── mode: str                 # 运行模式
    └── ...
            │
            ▼ 组合/继承
            │
AgentState (Agent 层 - core/agent/state)
    │
    ├── messages: Annotated[list, add_messages]  # 使用 add_messages 自动合并
    ├── task: Optional[Task]                      # 当前任务
    ├── subtasks: list[Task]                      # 子任务列表
    ├── results: dict[str, TaskResult]            # 结果映射
    └── agent_state: str                           # Agent 状态
```

**为什么不需要合并？**

- `GraphState` 是基础设施层的通用状态定义，供多个 Node 使用
- `AgentState` 是特化，通过 `add_messages` 实现 LangGraph 消息自动合并
- 不同层级的 Node 可能需要不同的 State 类型

### 8.2 Agent State 定义

```python
from typing import TypedDict, Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph import add_messages

# 引用基础设施层的 GraphState
from infra.graph import GraphState

class AgentState(GraphState):
    """Agent 状态定义 - 继承 GraphState，添加 Agent 特有字段"""
    messages: Annotated[list, add_messages]  # 消息列表（自动合并）
    task: Optional[Task]                      # 当前任务
    subtasks: list[Task]                      # 子任务列表
    mode: str                                 # 运行模式（lead/worker）
```

**为什么这样设计？**

- `messages` 使用 `add_messages` 实现 LangGraph 消息自动合并
- `task` 和 `subtasks` 支持树形任务结构
- `mode` 标识 Agent 当前模式