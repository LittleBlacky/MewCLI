# Agent 核心架构 - ReAct 循环

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. ReAct 循环

```
Agent ──→ 思考 ──→ 有工具调用？ ──→ Tool 执行 ──→ 回到 Agent
              │            │
              │            ↓
              │          没有
              │            ↓
              │          结束
```

**核心思想**：思考 → 行动 → 观察 → 循环直到完成

---

## 2. 状态定义

```python
class ReActState(TypedDict):
    """ReAct 执行状态"""
    session: SessionContext    # 会话上下文（包括所有消息）
    should_continue: bool      # 是否继续循环
```

---

## 3. 实现

```python
def build_react_graph() -> CompiledGraph:
    """构建 ReAct 子图"""
    builder = StateGraph(ReActState)

    builder.add_node("agent", agent_node)   # Agent 思考
    builder.add_node("tools", tool_node)     # 工具执行

    builder.add_edge(START, "agent")        # 从 agent 开始

    # agent 之后判断：去 tools 还是 end
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END},
    )

    # tools 执行完回到 agent
    builder.add_edge("tools", "agent")

    return builder.compile()
```

**流程**：

```
agent ──→ [判断] ──→ tools ──→ agent ──→ [判断] ──→ ... ──→ end
              │                              │
              ↓                              │
            end                             │
              ↑                              │
              └──────────────────────────────┘
```

**关键点**：
- `add_conditional_edges("agent", ...)` 在 agent 后判断
- `add_edge("tools", "agent")` tools 后直接回 agent
- agent 决定是否继续，不是 tools 决定

---

## 4. 节点

### Agent 节点

```python
async def agent_node(state: ReActState) -> ReActState:
    """Agent 思考"""
    session = state["session"]

    # 构建上下文（记忆 + 任务）
    context = build_context(state)

    # 检查容量，必要时压缩
    if session.should_compact():
        session.compact()

    # LLM 思考
    session.add_message(Message(role="user", content=context))
    tools = get_registry().to_langgraph_tools()
    response = await get_model().with_tools(tools, session.get_messages_for_llm())
    session.add_message(Message(role="assistant", content=response.content))

    return {
        "session": session,
        "should_continue": bool(getattr(response, 'tool_calls', None)),
    }
```

### Tool 节点

```python
async def tool_node(state: ReActState) -> ReActState:
    """执行工具，结果直接进 session.messages"""
    session = state["session"]

    tool_calls = getattr(session.messages[-1], 'tool_calls', None) or []

    for tc in tool_calls:
        result = execute_tool(tc)
        session.add_message(Message(
            role="tool",
            name=tc["name"],
            content=result,
        ))

    return {"session": session}
```

### 循环判断

```python
def should_continue(state: ReActState) -> str:
    """Agent 思考后判断：继续还是结束"""
    if state.get("should_continue"):
        return "continue"
    return "end"
```

---

## 5. Lead Agent 用 ReAct

**场景**：简单任务，直接执行（不分解）

```python
class LeadAgent:
    async def handle(self, user_input: str) -> str:
        if await self._needs_decompose(user_input):
            return await self._handle_with_workers(user_input)
        else:
            return await self._handle_direct(user_input)

    async def _handle_direct(self, task: str) -> str:
        """Lead 直接执行"""
        session = SessionContext()

        result = await self.react_graph.ainvoke({
            "session": session,
            "should_continue": True,
        })

        return result["session"].messages[-1].content
```

---

## 6. Worker Agent 用 ReAct

**场景**：执行 Lead 分配的子任务

```python
class WorkerAgent:
    async def execute(self, task: Task, context: dict) -> str:
        """Worker 执行子任务"""
        session = SessionContext()

        result = await self.react_graph.ainvoke({
            "session": session,
            "task_context": context,  # Lead 提供
            "should_continue": True,
        })

        return result["session"].messages[-1].content
```

---

## 7. 完整流程

```
                    用户输入
                        │
                        ▼
              ┌─────────────────┐
              │   Lead Agent    │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
          简单任务           复杂任务
              │                 │
              ▼                 ▼
        ┌───────────┐    ┌─────────────┐
        │ Lead 用   │    │ 分解成 N 个 │
        │ ReAct     │    │ 子任务      │
        └─────┬─────┘    └──────┬──────┘
              │                 │
              │                 ├──────┬──────┐
              │                 ▼      ▼      ▼
              │            Task 1  Task 2  Task 3
              │                 │      │      │
              │                 ▼      ▼      ▼
              │            ┌─────────────────┐
              │            │ Workers 用      │
              │            │ ReAct (各自执行) │
              │            └────────┬────────┘
              │                     │
              │                     ▼
              │            结果汇总给 Lead
              │                     │
              ▼                     ▼
            结果返回给用户 ◀────────┘
```

---

## 8. Lead vs Worker 的区别

### 8.1 上下文来源

| Agent | 上下文怎么来 | 能直接访问 memory |
|-------|-------------|------------------|
| Lead | `memory.preference.get_preferences()` | ✅ |
| Worker | `task_context` 参数（由 Lead 提供） | ❌ |

### 8.2 Lead Agent 用法

**场景**：用户说"帮我看看这个文件有什么问题"（简单任务）

```python
class LeadAgent:
    def __init__(self):
        self.react_graph = build_react_graph()
        self.memory = get_memory_layer()

    async def handle(self, user_input: str) -> str:
        # 简单任务，直接用 ReAct，Lead 自己构建上下文
        session = SessionContext()
        session.add_message(Message(
            role="system",
            content=self._build_system_prompt()
        ))
        session.add_message(Message(role="user", content=user_input))

        result = await self.react_graph.ainvoke({
            "session": session,
            "should_continue": True,
        })

        return result["session"].messages[-1].content

    def _build_system_prompt(self) -> str:
        """Lead 直接从 memory 获取偏好和知识"""
        parts = ["# 系统提示"]

        # 直接访问 memory
        prefs = self.memory.preference.get_preferences()
        if prefs:
            parts.append(f"\n## 用户偏好\n{prefs}")

        knowledge = self.memory.knowledge.get_project_knowledge()
        if knowledge:
            parts.append(f"\n## 项目知识\n{knowledge}")

        return "\n".join(parts)
```

### 8.3 Lead 分配任务给 Worker

**场景**：用户说"帮我重构这个项目"（复杂任务）

```python
class LeadAgent:
    async def handle_complex(self, task: str) -> str:
        # 1. LLM 分解任务
        subtasks = await self._decompose(task)

        # 2. 给每个子任务准备上下文
        worker_results = []
        for subtask in subtasks:
            context = self._prepare_context(subtask)

            # 3. 分配给 Worker
            worker = WorkerAgent()
            result = await worker.execute(subtask, context)
            worker_results.append(result)

        # 4. 汇总结果
        return self._summarize(worker_results)

    def _prepare_context(self, task: Task) -> dict:
        """Lead 决定给 Worker 什么上下文"""
        context = {}

        # 根据任务类型决定给什么
        if "文件" in task.description:
            context["knowledge"] = self.memory.knowledge.get_project_knowledge()

        if "代码风格" in task.description:
            context["preferences"] = self.memory.preference.get_preferences()

        # 找相关经验
        experiences = self.memory.episodic.search(task.description, limit=3)
        if experiences:
            context["experiences"] = experiences

        return context
```

### 8.4 Worker Agent 用法

**场景**：执行 Lead 分配的子任务

```python
class WorkerAgent:
    def __init__(self):
        self.react_graph = build_react_graph()

    async def execute(self, task: Task, context: dict) -> str:
        """Worker 执行子任务

        Args:
            task: 子任务描述
            context: Lead 提供的上下文（不是从 memory 直接获取）
        """
        session = SessionContext()

        # Worker 的 system prompt 来自 Lead
        session.add_message(Message(
            role="system",
            content=self._build_worker_prompt(task, context)
        ))

        result = await self.react_graph.ainvoke({
            "session": session,
            "should_continue": True,
        })

        return result["session"].messages[-1].content

    def _build_worker_prompt(self, task: Task, context: dict) -> str:
        """Worker 用 Lead 提供的上下文构建提示"""
        parts = [f"# 子任务\n{task.description}"]

        # 从 context 获取，不是直接访问 memory
        if context.get("knowledge"):
            parts.append(f"\n## 项目知识\n{context['knowledge']}")

        if context.get("preferences"):
            parts.append(f"\n## 用户偏好\n{context['preferences']}")

        if context.get("experiences"):
            parts.append(f"\n## 相关经验\n{context['experiences']}")

        return "\n".join(parts)
```

### 8.5 对比图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Lead Agent                               │
├─────────────────────────────────────────────────────────────────┤
│  用户输入                                                       │
│     │                                                          │
│     ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ context = memory.preference.get_preferences()  ← 直接访问 │
│  │ context += memory.knowledge.get_project_knowledge()       │   │
│  │                                                           │   │
│  │ ReAct 循环：agent → tools → agent → ... → end            │   │
│  └──────────────────────────────────────────────────────────┘   │
│     │                                                          │
│     ▼                                                          │
│  分配任务 + 上下文给 Workers                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       Worker Agent                              │
├─────────────────────────────────────────────────────────────────┤
│  Task + Context（由 Lead 提供）                                 │
│     │                                                          │
│     ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ context = task_context  ← 由 Lead 提供                    │   │
│  │ context 来自 Lead.memory，不是直接访问                     │   │
│  │                                                           │   │
│  │ ReAct 循环：agent → tools → agent → ... → end            │   │
│  └──────────────────────────────────────────────────────────┘   │
│     │                                                          │
│     ▼                                                          │
│  结果返回给 Lead                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 8.6 总结

| 项目 | Lead Agent | Worker Agent |
|------|------------|--------------|
| 上下文来源 | `memory.xxx.get_xxx()` | `task_context` 参数 |
| 谁能读 memory | ✅ 直接读 | ❌ 只能读 Lead 给的 |
| 谁能写 memory | ✅ | ❌ |
| ReAct 触发 | 简单任务直接执行 | 执行子任务 |

**核心区别**：Lead 直接访问 memory，Worker 通过 Lead 传入的 task_context 获取上下文

---

## 10. 相关文档

- [lead.md](lead.md) - Lead Agent 实现
- [worker.md](worker.md) - Worker Agent 实现
- [../session/context.md](../session/context.md) - SessionContext
- [../memory/index.md](../memory/index.md) - 记忆系统