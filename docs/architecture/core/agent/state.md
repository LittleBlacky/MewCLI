# Agent 核心架构 - 状态机定义

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Agent 生命周期状态机

```
                    ┌─────────────────┐
                    │     创建        │
                    │  (constructor)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     初始化      │
                    │   (initialize)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     就绪        │
                    │   (idle)       │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
       ┌────────────┐               ┌────────────┐
       │  执行任务  │               │   停止      │
       │  (running) │               │  (stopped)  │
       └─────┬──────┘               └─────────────┘
             │
             ▼
       ┌────────────┐
       │   完成     │
       │ (completed)│
       └────────────┘
```

---

## 2. 状态定义

### 2.1 Agent 状态

```python
class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"           # 空闲，等待任务
    RUNNING = "running"     # 执行中
    WAITING = "waiting"      # 等待子任务结果
    COMPLETED = "completed"   # 任务完成
    STOPPED = "stopped"      # 已停止
```

### 2.2 Worker 状态

```python
class WorkerState(Enum):
    """Worker 状态枚举"""
    IDLE = "idle"           # 空闲，等待分配
    BUSY = "busy"           # 执行任务中
    STOPPED = "stopped"     # 已停止
```

---

## 3. 状态转换规则

| 当前状态 | 事件 | 目标状态 | 说明 |
|----------|------|----------|------|
| IDLE | start_task() | RUNNING | 开始执行任务 |
| RUNNING | wait_subtasks() | WAITING | 等待子任务结果 |
| WAITING | all_subtasks_done() | COMPLETED | 所有子任务完成 |
| RUNNING | task_complete() | COMPLETED | 任务直接完成 |
| * | stop() | STOPPED | 强制停止 |

---

## 4. 状态机实现

```python
class AgentStateMachine:
    """Agent 状态机"""

    def __init__(self):
        self._state = AgentState.IDLE
        self._transitions = {
            AgentState.IDLE: [AgentState.RUNNING, AgentState.STOPPED],
            AgentState.RUNNING: [AgentState.WAITING, AgentState.COMPLETED, AgentState.STOPPED],
            AgentState.WAITING: [AgentState.COMPLETED, AgentState.STOPPED],
            AgentState.COMPLETED: [AgentState.STOPPED],
            AgentState.STOPPED: [],
        }

    def transition(self, event: str) -> bool:
        """状态转换"""
        next_state = self._get_next_state(self._state, event)
        if next_state:
            self._state = next_state
            return True
        return False

    def get_state(self) -> AgentState:
        """获取当前状态"""
        return self._state

    def _get_next_state(self, current: AgentState, event: str) -> Optional[AgentState]:
        """根据当前状态和事件获取下一个状态"""
        transitions = {
            (AgentState.IDLE, "start"): AgentState.RUNNING,
            (AgentState.IDLE, "stop"): AgentState.STOPPED,
            (AgentState.RUNNING, "wait"): AgentState.WAITING,
            (AgentState.RUNNING, "complete"): AgentState.COMPLETED,
            (AgentState.RUNNING, "stop"): AgentState.STOPPED,
            (AgentState.WAITING, "all_done"): AgentState.COMPLETED,
            (AgentState.WAITING, "stop"): AgentState.STOPPED,
            (AgentState.COMPLETED, "stop"): AgentState.STOPPED,
        }
        return transitions.get((current, event))
```

---

## 5. 与 LangGraph 集成

AgentState 继承 GraphState，通过 `add_messages` 实现消息自动合并：

```python
from typing import TypedDict, Optional, Annotated
from langgraph.graph import add_messages
from infra.graph import GraphState

class AgentState(GraphState):
    """Agent 状态定义"""
    messages: Annotated[list, add_messages]  # 消息列表（自动合并）
    task: Optional[Task]                      # 当前任务
    subtasks: list[Task]                      # 子任务列表
    agent_state: str                           # Agent 状态
```

---

## 6. 相关文档

- [base.md](base.md) - 核心类型定义
- [../infra/graph.md](../infra/graph.md) - GraphState 定义