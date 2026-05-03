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

## 2. 任务状态 (TaskStatus)

```python
class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"    # 待执行
    RUNNING = "running"   # 执行中
    DONE = "done"         # 已完成
    FAILED = "failed"     # 执行失败
    CANCELLED = "cancelled"  # 已取消
```

**状态机**：

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

## 3. 任务定义 (Task)

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

## 5. 任务结果 (TaskResult)

```python
@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str                    # 任务 ID
    success: bool                   # 是否成功
    output: Optional[str]           # 输出内容
    error: Optional[str]            # 错误信息
    duration: float                 # 执行时长（秒）
    metadata: dict = field(default_factory=dict)  # 额外元数据
```

---

## 6. 消息角色 (MessageRole)

```python
class MessageRole(Enum):
    """消息角色枚举"""
    SYSTEM = "system"    # 系统消息
    USER = "user"        # 用户消息
    ASSISTANT = "assistant"  # 助手消息
    TOOL = "tool"        # 工具返回消息
```

---

## 7. 消息定义 (Message)

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

## 8. Agent 配置 (AgentConfig)

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

## 9. 消息类型 (MessageType)

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

## 9. 任务分解类型

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


class ComplexityResult(BaseModel):
    """复杂度判断结果 - 用于判断是否需要分解"""
    should_decompose: bool = Field(description="是否需要分解为多个子任务")
    complexity_level: str = Field(description="复杂度等级: low / medium / high")
    reason: str = Field(description="判断理由")
```

## 10. 执行模式

MiniCode 支持两种执行模式：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **ReAct** | 边做边想，工具调用后立即分析 | 简单任务（默认） |
| **Plan-and-Solve** | 先制定计划，再按计划执行 | 复杂任务 |

详细设计见：[plan_and_solve.md](plan_and_solve.md)

---

## 11. AgentState 定义

**Plan-and-Solve（计划-执行）** 是一种两阶段执行模式，适用于复杂任务：

```
用户输入
    │
    ▼
┌─────────────────┐
│   Plan Phase    │  ← 分析任务，制定计划
│   (计划阶段)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Execute Phase  │  ← 按计划逐步执行
│   (执行阶段)     │
└─────────────────┘
```

### 10.2 阶段划分

| 阶段 | 职责 | 关键操作 |
|------|------|---------|
| **Plan** | 分析任务，拆解步骤 | 理解意图 → 分解子任务 → 生成步骤列表 |
| **Execute** | 按计划执行每步 | 执行 → 验证 → 记录结果 |

### 10.3 Plan 结构

```python
@dataclass
class PlanStep:
    """计划步骤"""
    step_id: str                    # 步骤 ID
    description: str               # 步骤描述
    action: str                    # 执行的工具/动作
    depends_on: list[str] = []    # 依赖的前置步骤
    result: Optional[str] = None   # 执行结果
    status: str = "pending"        # pending / running / done / failed


@dataclass
class Plan:
    """完整计划"""
    goal: str                      # 最终目标
    steps: list[PlanStep]          # 步骤列表
    context: str                   # 上下文信息
    created_at: float = field(default_factory=time.time)
```

### 10.4 执行流程图

```
                    ┌──────────────┐
                    │  planner     │  ← 分析任务，生成计划
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐     │     ┌──────▼──────┐
       │  execute    │     │     │  execute    │
       │  step_1    │     │     │  step_n     │
       └──────┬──────┘     │     └──────┬──────┘
              │            │            │
       ┌──────▼──────┐     │     ┌──────▼──────┐
       │  verify     │     │     │  verify     │
       │  step_1    │     │     │  step_n    │
       └──────┬──────┘     │     └──────┬──────┘
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │    done      │
                    └──────────────┘
```

### 10.5 Planner Node 实现

```python
async def planner_node(state: AgentState) -> dict:
    """生成计划节点"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    analysis_prompt = f"""
分析任务：{last_message}

生成执行计划（JSON）：
{{"goal": "...", "steps": [
  {{"step_id": "1", "description": "...", "action": "..."}}
]}}
"""
    response = await llm.ainvoke([HumanMessage(content=analysis_prompt)])
    plan_data = json.loads(response.content)

    return {
        "plan": Plan(**plan_data),
        "mode": "execute",
    }
```

### 10.6 Execute Node 实现

```python
async def execute_step(step: PlanStep, context: dict) -> dict:
    """执行单个步骤"""
    # 1. 检查依赖
    for dep_id in step.depends_on:
        dep_step = context["plan"].get_step(dep_id)
        if dep_step.status != "done":
            return {"blocked": True, "reason": f"等待依赖 {dep_id}"}

    # 2. 执行工具调用
    tool_result = await tool_node.invoke({
        "messages": [HumanMessage(content=step.action)]
    })

    return {
        "step_id": step.step_id,
        "result": tool_result,
        "status": "done",
    }
```

### 10.7 Verify Node 实现

```python
async def verify_node(step: PlanStep) -> dict:
    """验证步骤结果"""
    if not step.result:
        return {"status": "failed", "reason": "无执行结果"}

    verify_prompt = f"""
步骤：{step.description}
结果：{step.result}

验证是否完成预期目标，返回：
{{"passed": true/false, "need_retry": true/false, "reason": "..."}}
"""
    response = await llm.ainvoke([HumanMessage(content=verify_prompt)])
    return json.loads(response.content)
```

### 10.8 主流程

```python
async def plan_and_solve(user_input: str) -> str:
    """Plan-and-Solve 主流程"""
    state = create_initial_state([HumanMessage(user_input)])

    # Phase 1: Plan
    plan_result = await planner_node(state)
    state["plan"] = plan_result["plan"]

    # Phase 2: Execute
    for step in state["plan"].steps:
        step_result = await execute_step(step, state)
        state["plan"].update_step(step_result)

        verify_result = await verify_node(step)
        if verify_result["status"] == "failed":
            return f"步骤 {step.step_id} 执行失败"

        if verify_result.get("need_retry"):
            step_result = await execute_step(step, state)

    return state["plan"].steps[-1].result
```

### 10.9 与 ReAct 模式对比

| 维度 | ReAct | Plan-and-Solve |
|------|-------|----------------|
| 适用场景 | 简单任务、快速响应 | 复杂任务、多步骤 |
| 执行方式 | 边想边做 | 先计划后执行 |
| 步骤控制 | 动态决定 | 预先规划 |
| 响应速度 | 快 | 慢（需要先计划） |

### 10.10 模式切换

```python
class Agent:
    def _should_use_plan_mode(self, user_input: str) -> bool:
        """判断是否需要 Plan 模式"""
        return (
            len(user_input) > 100 or
            any(kw in user_input for kw in ["计划", "实现", "架构", "设计", "分解"])
        )
```

---

## 11. AgentState 定义

### 11.1 精简设计

```python
class AgentState(TypedDict):
    """Agent 状态 - 消息流"""
    messages: Annotated[list, add_messages]  # 消息列表（用户 + AI + 工具，自动合并）
    last_summary: str                        # 最后摘要
    mode: str                                 # 执行模式（plan / execute）
    task_count: int                          # 任务计数
```

### 11.2 状态结构

```
AgentState (消息流)
├── messages: list              # 所有消息（用户 + AI + 工具结果）
├── last_summary: str          # 摘要
├── mode: str                   # 模式（plan / execute）
└── task_count: int            # 计数
```

### 11.3 模块绑定机制

```
Session (thread_id = "abc123")
    │
    ├── thread_id: str                  # 绑定 key
    │
    ├── MemoryLayer("abc123")           # 记忆层（独立管理）
    │   └── 状态存到 .minicode/memory/
    │
    ├── TaskManager("abc123")           # 任务管理（独立管理）
    │   └── 状态存到 .minicode/tasks/
    │
    ├── TeamManager("abc123")           # 团队管理（独立管理）
    │   └── 状态存到 .minicode/team/
    │
    └── ExecutionController("abc123")   # 执行控制（独立管理）
        └── 内存状态，thread_id 标记

AgentState
└── messages: list              # 消息流（唯一共享）
```

### 11.4 设计原则

1. **AgentState 精简** - 只负责消息流和核心配置
2. **模块独立** - 各模块（Memory、Task、Team、Execution）自己管理状态
3. **thread_id 绑定** - 所有模块通过 thread_id 关联同一会话
4. **各模块持久化** - 每个模块按 thread_id 存储到自己的目录

### 11.5 各模块状态管理

| 模块 | 状态管理方式 | 持久化位置 |
|------|-------------|-----------|
| MemoryLayer | 独立管理 Preference/Knowledge/Episodic | `.minicode/memory/{thread_id}/` |
| TaskManager | 独立管理 task_items/pending_tasks | `.minicode/tasks/{thread_id}/` |
| TeamManager | 独立管理 teammates/results | `.minicode/team/{thread_id}/` |
| AgentState | 仅消息流 | 不持久化（由 Session 管理） |

参考实现：`src/minicode/agent/state.py`

---

## 12. 与 LangGraph 的关系

AgentState 使用 `TypedDict`，不是继承 `GraphState`，而是独立定义。

两者都使用 `add_messages` 实现消息自动合并，但职责不同：

| 类型 | 定义位置 | 用途 |
|------|---------|------|
| **GraphState** | `infra/graph.py` | LangGraph 基础设施层 |
| **AgentState** | `core/agent/state.py` | Agent 业务逻辑层 |