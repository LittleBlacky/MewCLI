# Agent 核心架构 - Lead Agent

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Lead Agent 职责

Lead Agent 是系统的核心执行单元，负责：

1. **理解用户意图** - 解析用户输入，确定任务目标
2. **智能分解任务** - 使用 LLM 动态决定子任务数量和类型
3. **分配子任务** - 将子任务分配给 Workers
4. **监控执行状态** - 追踪子任务执行进度
5. **汇总结果** - 合并 Worker 结果，生成最终回复

---

## 2. Lead Agent 架构

```
Lead Agent
    │
    ├── System Prompt（角色定义）
    │   └── "你是 Lead Agent，负责理解任务、分解任务、汇总结果"
    │
    ├── 输入处理
    │   ├── 解析用户意图
    │   ├── 检索记忆（Preference、Knowledge）
    │   └── 构建上下文
    │
    ├── 任务分解（LLM 推理）
    │   ├── 判断是否需要分解
    │   ├── 决定分解策略
    │   └── 生成子任务列表
    │
    ├── 任务分配
    │   ├── 与 Team Manager 交互
    │   ├── 分配任务给 Workers
    │   └── 追踪分配状态
    │
    ├── 结果汇总
    │   ├── 收集 Worker 结果
    │   ├── 合并结果
    │   └── 生成最终回复
    │
    └── 触发进化
        └── 后台通知 Evolution Engine
```

---

## 3. Lead Agent 核心方法

### 4.1 理解用户意图

```python
async def understand(self, user_input: str) -> str:
    """理解用户意图"""
    # 1. 检索相关记忆
    memories = self.memory.retrieve(user_input)

    # 2. 构建上下文
    context = self._build_context(user_input, memories)

    # 3. LLM 推理
    return await self.llm.think(context)

def _build_context(self, user_input: str, memories: dict) -> str:
    """构建上下文"""
    parts = [f"# 用户输入\n{user_input}"]

    if memories.get("preference"):
        parts.append(f"\n# 用户偏好\n{memories['preference']}")
    if memories.get("knowledge"):
        parts.append(f"\n# 项目知识\n{memories['knowledge']}")
    if memories.get("episodic"):
        parts.append(f"\n# 相关经验\n{memories['episodic']}")

    return "\n\n".join(parts)
```

### 4.2 智能分解任务

```python
async def decompose(self, task: str) -> list[Task]:
    """智能分解任务（结构化输出 + 验证 + 重试）"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            result = await self.llm.with_structured_output(
                DecompositionResult,
                prompt=f"任务: {task}\n\n请判断并分解..."
            )

            # 不需要分解，直接返回原任务
            if not result.should_decompose:
                return [Task(description=task)]

            # 构建任务列表
            return self._build_tasks(result.subtasks)

        except Exception as e:
            logger.warning(f"分解结果验证失败，重试 ({attempt + 1}/{max_retries}): {e}")
            continue

    # 全部失败，返回原任务
    return [Task(description=task)]

def _build_tasks(self, subtasks: list[SubTask]) -> list[Task]:
    """根据子任务定义构建任务对象"""
    tasks = []
    for i, st in enumerate(subtasks):
        task = Task(
            id=f"task_{i}",
            description=st.description,
            status=TaskStatus.PENDING,
            created_at=time.time(),
        )
        for dep_id in st.dependencies:
            task.children_ids.append(dep_id)
        tasks.append(task)
    return tasks
```

### 4.3 分配任务

```python
async def assign(self, subtasks: list[Task]) -> dict[str, str]:
    """分配任务给 Workers"""
    assignments = {}
    for task in subtasks:
        worker_id = await self.team_manager.assign_task(task)
        assignments[task.id] = worker_id
    return assignments
```

### 4.4 汇总结果

```python
async def aggregate(self, results: dict[str, TaskResult]) -> str:
    """汇总 Worker 结果"""
    # 1. 合并所有结果
    combined = "\n".join(r.result for r in results.values() if r.success)

    # 2. 生成最终回复
    prompt = f"合并以下结果并生成最终回复：\n{combined}"
    return await self.llm.think(prompt)
```

---

## 4. LangGraph 节点实现

节点实现详见第4节源码 `build_lead_graph()` 函数。

### 5.1 状态定义

```python
class LeadGraphState(TypedDict):
    session: SessionContext
    task: Optional[str]
    should_decompose: bool
    subtasks: list[Task]
    assignments: dict[str, str]          # {task_id: worker_id}
    results: dict[str, TaskResult]       # {worker_id: result}
    final_response: Optional[str]
```

### 5.2 节点列表

| 节点 | 函数 | 说明 |
|------|------|------|
| understand | `understand_node` | 理解用户意图 |
| should_decompose | `should_decompose_node` | 判断是否需要分解 |
| decompose | `decompose_node` | 分解任务 |
| execute_direct | `execute_direct_node` | 调用 ReAct 执行 |
| assign_tasks | `assign_tasks_node` | 分配给 Workers |
| aggregate | `aggregate_node` | 汇总结果 |

### 5.3 执行流程图

```
                    用户输入
                        │
                        ▼
              ┌─────────────────────┐
              │      understand     │
              │    (理解意图)        │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  should_decompose  │
              │   (判断是否分解)     │
              └──────────┬──────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
    ┌───────────────┐         ┌───────────────┐
    │   decompose  │         │ execute_direct│
    │   (分解任务)  │         │   (ReAct 执行) │
    └───────┬───────┘         └───────┬───────┘
            │                         │
            ▼                         │
    ┌───────────────┐                 │
    │  assign_tasks │                 │
    │  (分配 Workers)│                │
    └───────┬───────┘                 │
            │                         │
            └────────────┬────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │      aggregate     │
              │    (汇总结果)       │
              └──────────┬──────────┘
                         │
                         ▼
                      END
```

### 5.4 ReAct 子图

`execute_direct_node` 调用 ReAct 子图处理简单任务。

详见：[react.md](react.md)

```
Lead Agent 和 Worker Agent 共用同一个 ReAct 子图：

┌──────────────────────────────────────────────────────────┐
│                     SessionContext                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │ messages: [...] │ capacity 管理 │ compact()     │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │   Agent   │───►│   Tools   │───►│   观察     │
  │  (记忆+   │    │ (ToolReg)  │    │ (存到      │
  │  tool_res)│    │            │    │ tool_res)  │
  └────────────┘    └────────────┘    └─────┬─────┘
       ▲                                   │
       └───────────────────────────────────┘
                   (循环直到无工具调用)
```

**复用场景**：
- Lead Agent：`execute_direct_node` 调用 ReAct 执行简单任务
- Worker Agent：执行子任务

---

## 5. 与其他模块集成

### 6.1 与 Skill 集成

```python
class LeadAgent:
    async def understand_and_match(self, user_input: str) -> str:
        """理解输入并匹配技能"""
        # 1. 匹配技能
        matched_skills = self.skill_registry.match(user_input, self.context)

        # 2. 构建上下文
        context = user_input
        for skill in matched_skills:
            context += f"\n\n## 相关技能: {skill.name}\n{skill.content}"
            skill.usage_count += 1

        # 3. 理解意图
        return await self.llm.think(context)
```

### 6.2 与 Team Manager 集成

Lead Agent 通过 Team Manager（位于 `core/team/manager.py`）分配任务给 Workers：

```python
from core.team.manager import TeamManager

async def assign_tasks_to_workers(self, subtasks: list[Task]) -> dict[str, str]:
    """分配子任务给 Workers"""
    team_manager = TeamManager()
    assignments = {}
    for task in subtasks:
        worker_id = await team_manager.assign_task(task)
        assignments[task.id] = worker_id

    # 注册完成回调
    for task_id, worker_id in assignments.items():
        team_manager.on_task_completed(
            task_id=task_id,
            callback=lambda result: self.handle_worker_result(result)
        )
    return assignments
```

```
Lead Agent ──assign_task()──> Team Manager ──dispatch──> Workers
                           │
                           <──on_task_completed()──
```

详见：[../team/index.md](../team/index.md)

---

## 6. 关键设计决策

| 决策项        | 选择     | 说明                   |
| ------------- | -------- | ---------------------- |
| 使用 LLM 分解 | 动态决定 | 根据任务特点自适应分解 |
| Lead 负责汇总 | 集中管理 | 统一生成最终回复       |
| 与 Skill 集成 | 技能匹配 | 任务开始时匹配相关技能 |
| 与 Evolution 集成 | 后台通知 | 任务完成后通知进化引擎 |

---

## 7. 完整源码

```python
"""
Lead Agent - 核心执行单元
负责理解意图、智能分解任务、分配 Workers、汇总结果
"""

import time
import logging
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, END

from core.agent.base import (
    Task, TaskStatus, TaskResult,
    SubTask, DecompositionResult, ComplexityResult
)
from core.memory import get_memory_layer
from core.session import SessionContext, Message
from core.team.manager import TeamManager
from core.evolution.engine import EvolutionEngine
from infra.model import get_model

logger = logging.getLogger(__name__)


class LeadGraphState(TypedDict):
    """Lead Agent 执行图状态"""
    session: SessionContext
    task: Optional[str]
    should_decompose: bool
    subtasks: list[Task]
    assignments: dict[str, str]
    results: dict[str, TaskResult]
    final_response: Optional[str]


# ============ 节点实现 ============

async def understand_node(state: LeadGraphState) -> LeadGraphState:
    """节点1: 理解用户意图"""
    memory = get_memory_layer()
    session = state["session"]
    user_input = state.get("messages", [{}])[-1].get("content", "")

    memories = memory.retrieve(user_input)

    context_parts = [f"# 用户输入\n{user_input}"]
    if memories.get("preference"):
        context_parts.append(f"\n# 用户偏好\n{memories['preference']}")
    if memories.get("knowledge"):
        context_parts.append(f"\n# 项目知识\n{memories['knowledge']}")
    if memories.get("episodic"):
        context_parts.append(f"\n# 相关经验\n{memories['episodic']}")

    context = "\n\n".join(context_parts)

    session.add_message(Message(role="user", content=context))

    if session.should_compact():
        session.compact(keep_recent=5)

    messages = session.get_messages_for_llm()
    response = await get_model().think(messages)

    session.add_message(Message(role="assistant", content=response))

    return {"session": session, "task": response}


async def should_decompose_node(state: LeadGraphState) -> str:
    """节点2: 判断是否需要分解"""
    task = state.get("task", "")
    complexity = await get_model().with_structured_output(
        ComplexityResult,
        prompt=f"任务: {task}\n\n判断是否需要分解..."
    )
    return "decompose" if complexity.should_decompose else "execute_direct"


async def decompose_node(state: LeadGraphState) -> LeadGraphState:
    """节点3: 分解任务"""
    task = state.get("task", "")

    for attempt in range(3):
        try:
            result = await get_model().with_structured_output(
                DecompositionResult,
                prompt=f"任务: {task}\n\n请分解..."
            )

            if not result.should_decompose:
                return {"subtasks": [Task(description=task)], "should_decompose": False}

            tasks = _build_tasks(result.subtasks)
            return {"subtasks": tasks, "should_decompose": True}

        except Exception as e:
            logger.warning(f"分解失败，重试 ({attempt + 1}/3): {e}")
            continue

    return {"subtasks": [Task(description=task)], "should_decompose": False}


def _build_tasks(subtasks: list[SubTask]) -> list[Task]:
    """构建 Task 对象"""
    tasks = []
    for i, st in enumerate(subtasks):
        task = Task(
            id=f"task_{i}",
            description=st.description,
            status=TaskStatus.PENDING,
            created_at=time.time(),
        )
        for dep_id in st.dependencies:
            task.children_ids.append(dep_id)
        tasks.append(task)
    return tasks


async def execute_direct_node(state: LeadGraphState) -> LeadGraphState:
    """节点4: 调用 ReAct 子图执行"""
    from core.agent.react import build_react_graph

    session = state["session"]
    task = state.get("task", "")

    react_graph = build_react_graph()
    result = await react_graph.ainvoke({
        "messages": session.get_messages_for_llm(),
        "task": task
    })

    return {"results": {"main": TaskResult(success=True, result=str(result))}}


async def assign_tasks_node(state: LeadGraphState) -> LeadGraphState:
    """节点5: 分配子任务"""
    team_manager = TeamManager()
    subtasks = state.get("subtasks", [])
    assignments = {}

    for task in subtasks:
        worker_id = await team_manager.assign_task(task)
        assignments[task.id] = worker_id

    return {"assignments": assignments}


async def aggregate_node(state: LeadGraphState) -> LeadGraphState:
    """节点6: 汇总结果"""
    results = state.get("results", {})
    combined = "\n".join(r.result for r in results.values() if r.success)

    response = await get_model().think(f"合并以下结果并生成最终回复:\n{combined}")

    if combined:
        await _trigger_evolution(state.get("task", ""), results, {"aggregated": response})

    return {"final_response": response}


async def _trigger_evolution(task: str, results: dict, context: dict):
    """触发进化引擎"""
    try:
        evolution = EvolutionEngine()
        await evolution.notify(
            trigger="task_completed",
            task=task,
            results={k: v.result for k, v in results.items()},
            context=context
        )
    except Exception as e:
        logger.warning(f"触发进化失败: {e}")


# ============ 构建图 ============

def build_lead_graph():
    """构建 Lead Agent 执行图"""
    builder = StateGraph(LeadGraphState)

    builder.add_node("understand", understand_node)
    builder.add_node("should_decompose", should_decompose_node)
    builder.add_node("decompose", decompose_node)
    builder.add_node("execute_direct", execute_direct_node)
    builder.add_node("assign_tasks", assign_tasks_node)
    builder.add_node("aggregate", aggregate_node)

    builder.add_edge("understand", "should_decompose")

    builder.add_conditional_edges(
        "should_decompose",
        lambda state: "decompose" if state["should_decompose"] else "execute_direct"
    )

    builder.add_edge("decompose", "assign_tasks")
    builder.add_edge("execute_direct", "aggregate")
    builder.add_edge("assign_tasks", "aggregate")
    builder.add_edge("aggregate", END)

    return builder.compile()


# ============ 入口类 ============

class LeadAgent:
    """Lead Agent 主入口"""

    def __init__(self):
        self.memory = get_memory_layer()
        self.llm = get_model()
        self.team_manager = TeamManager()
        self.graph = build_lead_graph()

    async def run(self, user_input: str, session: SessionContext) -> str:
        """执行主流程"""
        result = await self.graph.ainvoke({
            "session": session,
            "messages": [{"role": "user", "content": user_input}],
            "task": None,
            "should_decompose": False,
            "subtasks": [],
            "assignments": {},
            "results": {},
            "final_response": None
        })
        return result.get("final_response", "")
```

---

## 8. 相关文档

- [base.md](base.md) - 核心类型定义
- [worker.md](worker.md) - Worker Agent 实现
- [../team/index.md](../team/index.md) - Team 协作架构

