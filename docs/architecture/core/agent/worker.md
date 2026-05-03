# Agent 核心架构 - Worker Agent

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Worker Agent 职责

Worker Agent 是任务的执行单元，负责：

1. **接收任务** - 从 Team Manager 接收分配的子任务
2. **执行任务** - 使用工具完成具体任务
3. **报告结果** - 将执行结果返回给 Team Manager
4. **参与进化** - 记录执行过程供 Evolution Engine 分析

---

## 2. Worker Agent 架构

```
Worker Agent
    │
    ├── System Prompt（角色定义）
    │   └── "你是 Worker Agent，负责执行分配的任务"
    │
    ├── 任务接收
    │   ├── 监听 Inbox
    │   ├── 解析任务描述
    │   └── 准备执行环境
    │
    ├── 任务执行
    │   ├── 调用 LLM 制定计划
    │   ├── 使用工具执行
    │   ├── 处理错误和重试
    │   └── 收集执行结果
    │   │
    │   └── 执行模式（可配置）
    │       ├── ReAct：边做边想，快速响应
    │       └── Plan-and-Solve：先计划再执行，更稳健
    │
    └── 结果报告
        ├── 格式化结果
        ├── 通知 Team Manager
        └── 记录执行日志
```

---

## 3. Worker Agent 核心方法

```python
class WorkerAgent:
    """Worker Agent 实现"""

    async def receive(self) -> Optional[Task]:
        """从 Inbox 接收任务"""
        message = await self.inbox.receive()
        if message and message.type == "task":
            return self.parse_task(message)
        return None

    async def execute(self, task: Task, mode: str = "default") -> TaskResult:
        """执行任务

        Args:
            task: 要执行的任务
            mode: 执行模式，"default"=ReAct，"plan"=Plan-and-Solve
        """
        start_time = time.time()

        try:
            # 1. 理解任务（根据模式选择策略）
            plan = await self.plan(task.description, mode=mode)

            # 2. 执行计划
            for step in plan:
                result = await self.execute_step(step)

                # 检查是否需要工具
                if result.requires_tool:
                    tool_result = await self.call_tool(result.tool_name, result.tool_args)
                    result = self.process_tool_result(tool_result)

                # 检查错误
                if result.is_error:
                    raise ExecutionError(result.error)

            # 3. 生成结果
            return TaskResult(
                task_id=task.id,
                success=True,
                result=result.content,
                duration=time.time() - start_time,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    async def call_tool(self, tool_name: str, tool_args: dict) -> str:
        """调用工具

        注意：
        - I/O 工具必须用 asyncio.create_subprocess_* 实现真正异步
        - 纯 Python CPU 任务无法通过线程并行（GIL 限制），需用 multiprocessing
        - to_thread 仅适合：调用同步 I/O 库 或 会释放 GIL 的 C 扩展
        """
        tool = self.tool_registry.get(tool_name)
        if not tool:
            return f"[Error] Tool '{tool_name}' not found"

        # 异步工具（create_subprocess_* / aiofiles）直接调用
        # 同步工具用 to_thread：阻塞 I/O 移到线程池，避免阻塞事件循环
        if tool.is_async:
            return await tool.execute(**tool_args)
        else:
            return await asyncio.to_thread(
                lambda: tool.execute(**tool_args)
            )

    async def report(self, result: TaskResult) -> None:
        """报告结果给 Team Manager"""
        await self.team_manager.on_task_completed(result.task_id, result)
```

---

## 4. Worker 执行流程

```
                    ┌─────────────────┐
                    │    接收任务     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    理解任务     │
                    │   (LLM 分析)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    制定计划     │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
       ┌────────────┐               ┌────────────┐
       │ 需要工具   │               │ 不需要工具 │
       └─────┬──────┘               └──────┬─────┘
             │                              │
             ▼                              │
    ┌────────────────┐                      │
    │   调用工具     │                      │
    └────┬───────────┘                      │
         │                                  │
         ▼                                  │
    ┌────────────────┐                      │
    │  处理工具结果  │                      │
    └────┬───────────┘                      │
         │                                  │
         └──────────┬───────────────────────┘
                    │
                    ▼
           ┌─────────────────┐
           │    任务完成？   │
           └────────┬────────┘
                    │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
   ┌───────────┐      ┌───────────┐
   │   成功     │      │   失败    │
   └─────┬─────┘      └─────┬─────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
           ┌─────────────────┐
           │   报告结果     │
           └─────────────────┘
```

---

## 5. LangGraph Node 实现

```python
# Worker Node
async def worker_node(state: AgentState) -> AgentState:
    """Worker Agent 处理节点"""
    subtasks = state.get("subtasks", [])

    # 执行所有子任务
    results = {}
    for task in subtasks:
        result = await worker.execute(task)
        results[task.id] = result

    # 汇总结果
    final_result = await lead.aggregate(results)

    return {
        **state,
        "results": results,
        "final_result": final_result,
    }
```

---

## 6. 与 ReAct 子图集成

Worker Agent 使用共用的 ReAct 子图执行工具调用循环：

```python
class WorkerAgent:
    def __init__(self):
        from core.agent.react import build_react_graph
        self.react_graph = build_react_graph()

    async def execute_task(self, task: Task) -> str:
        """使用 ReAct 子图执行任务"""
        session = SessionContext(thread_id=self.thread_id)
        session.add_message(Message(role="system", content=WORKER_SYSTEM_PROMPT))

        result = await self.react_graph.ainvoke({
            "session": session,
            "task": task.description,
            "tool_results": [],
            "should_continue": True,
        })

        return result["session"].messages[-1].content
```

详见：[react.md](react.md)（完整实现、容量管理、与 Lead 集成说明）

---

## 7. 与其他模块集成

### 6.1 与 Team Manager 集成

Worker 通过 Team Manager 接收任务和报告结果：

```
Team Manager ──dispatch──> Worker
                          │
                          <──on_task_completed()──
```

### 6.2 技能访问模式

**技能访问权限**：Lead Agent 读写，Worker 只读

| 操作      | Lead Agent | Worker Agent |
| --------- | ---------- | ------------ |
| 创建技能  | ✓          | ✗            |
| 更新技能  | ✓          | ✗            |
| 匹配技能  | ✓          | ✓            |
| 删除技能  | ✓          | ✗            |

**设计理由**：
- **Lead 负责生成**：Evolution Engine 生成的新技能由 Lead Agent 注册
- **Worker 专注使用**：Worker Agent 只需匹配和使用已有技能
- **统一入口**：避免多 Agent 同时写入导致的数据冲突

---

## 7. 关键设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 执行模式可选 | ReAct / Plan-and-Solve | 根据任务类型选择 |
| 异步工具调用 | to_thread | 避免阻塞事件循环 |
| Worker 只读 Skill | 集中管理 | 避免数据冲突 |

---

## 8. 相关文档

- [base.md](base.md) - 核心类型定义
- [lead.md](lead.md) - Lead Agent 实现
- [react.md](react.md) - ReAct 子图（Lead/Worker 共用）
- [../team/index.md](../team/index.md) - Team 协作架构