# Plan-and-Solve LangGraph 设计

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 状态设计

```python
class PlanAndSolveState(TypedDict):
    """Plan-and-Solve 状态"""
    # 消息流
    messages: Annotated[list, add_messages]

    # 计划相关
    plan: Optional[Plan]           # 当前计划（Plan 阶段后填充）
    step_index: int = 0            # 当前执行到第几步

    # 上下文
    user_input: str                # 原始用户输入
    current_step_result: str       # 当前步骤的执行结果

    # 元数据
    mode: str = "plan"             # plan / execute / verify / done
    step_results: list[str]        # 所有步骤的结果
```

---

## 2. 数据结构

```python
@dataclass
class PlanStep:
    """计划步骤"""
    step_id: str
    description: str
    action: str                    # 要执行的工具/动作描述
    depends_on: list[str] = []    # 依赖的前置步骤 ID
    result: str = ""
    status: str = "pending"       # pending / running / done / failed


@dataclass
class Plan:
    """完整计划"""
    goal: str
    steps: list[PlanStep]
    created_at: float = field(default_factory=time.time)

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_next_ready_step(self) -> Optional[PlanStep]:
        """获取下一个可以执行的步骤（依赖都已完成）"""
        for step in self.steps:
            if step.status != "pending":
                continue
            deps_done = all(
                self.get_step(dep_id).status == "done"
                for dep_id in step.depends_on
            )
            if deps_done:
                return step
        return None
```

---

## 3. 图结构

```
                    ┌─────────────┐
                    │   start     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   planner   │  ← 生成 Plan
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   should    │  ← 有步骤可执行？
                    │   execute   │
                    └───┬─────┬───┘
                        │     │
                       yes    no
                        │     │
                        ▼     │
              ┌─────────────────┐
              │                 │
              │  ┌───────▼──────┐
              │  │   execute   │  ← 执行当前步骤
              │  │   step      │
              │  └───────┬──────┘
              │          │
              │  ┌───────▼──────┐
              │  │   verify    │  ← 验证结果
              │  │   result    │
              │  └───┬─────┬───┘
              │      │     │
              │    pass  fail
              │      │     │
              │      │     ▼
              │      │  ┌────────────┐
              │      │  │  retry or  │
              │      │  │   abort    │
              │      │  └────────────┘
              │      │
              └──────┴────────────┘
                         │
                    ┌────▼──────┐
                    │   done    │
                    └───────────┘
```

---

## 4. 节点实现

### 4.1 Planner Node

```python
def planner_node(state: PlanAndSolveState) -> dict:
    """分析任务，生成计划"""
    user_input = state["user_input"]

    prompt = f"""
分析以下任务，生成执行计划：

任务：{user_input}

请以 JSON 格式返回计划：
{{
    "goal": "任务目标描述",
    "steps": [
        {{
            "step_id": "1",
            "description": "步骤描述",
            "action": "具体要做什么",
            "depends_on": []
        }}
    ]
}}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    plan_data = json.loads(response.content)

    return {
        "plan": Plan(**plan_data),
        "mode": "execute",
        "step_index": 0,
        "step_results": [],
    }
```

### 4.2 Execute Node

```python
def execute_node(state: PlanAndSolveState) -> dict:
    """执行当前步骤"""
    plan = state["plan"]
    step = plan.get_next_ready_step()

    if not step:
        return {"mode": "done"}

    # 更新步骤状态
    step.status = "running"

    # 调用工具执行
    tool_result = invoke_tool(step.action)

    # 记录结果
    step.result = tool_result
    step.status = "done"

    return {
        "current_step_result": tool_result,
        "step_results": state.get("step_results", []) + [tool_result],
    }
```

### 4.3 Verify Node

```python
def verify_node(state: PlanAndSolveState) -> dict:
    """验证步骤结果"""
    current_result = state.get("current_step_result", "")

    prompt = f"""
验证以下执行结果：

步骤：{state["plan"].steps[state["step_index"]].description}
结果：{current_result}

判断：
1. 是否完成了预期目标？
2. 是否有错误或异常？
3. 是否需要重试？

返回 JSON：
{{"status": "pass | fail | retry", "reason": "..."}}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    result = json.loads(response.content)

    if result["status"] == "retry":
        # 重试当前步骤
        return {"mode": "execute"}

    if result["status"] == "fail":
        # 计划失败
        return {"mode": "done", "error": result["reason"]}

    # 继续下一个步骤
    return {
        "mode": "execute",
        "step_index": state["step_index"] + 1,
    }
```

---

## 5. 边定义

```python
from langgraph.graph import StateGraph

builder = StateGraph(PlanAndSolveState)

# 添加节点
builder.add_node("planner", planner_node)
builder.add_node("execute", execute_node)
builder.add_node("verify", verify_node)

# 设置入口
builder.set_entry_point("planner")

# 边
builder.add_edge("planner", "execute")

# 条件边
def should_continue(state: PlanAndSolveState) -> str:
    plan = state["plan"]
    if not plan:
        return "execute"

    # 检查是否还有未完成的步骤
    next_step = plan.get_next_ready_step()
    if next_step:
        return "execute"
    return "done"

builder.add_conditional_edges(
    "execute",
    should_continue,
    {
        "execute": "verify",
        "done": END,
    }
)

builder.add_edge("verify", "execute")
```

---

## 6. 完整图构建

```python
def build_plan_and_solve_graph() -> CompiledGraph:
    """构建 Plan-and-Solve 图"""
    builder = StateGraph(PlanAndSolveState)

    # 节点
    builder.add_node("planner", planner_node)
    builder.add_node("execute", execute_node)
    builder.add_node("verify", verify_node)

    # 边
    builder.add_edge("__start__", "planner")
    builder.add_edge("planner", "execute")

    # 循环：execute → verify → execute
    builder.add_edge("execute", "verify")
    builder.add_edge("verify", "execute")

    # 结束条件
    builder.add_conditional_edges(
        "execute",
        lambda s: "done" if s.get("plan") and not s["plan"].get_next_ready_step() else "verify",
        {"done": "__end__", "verify": "verify"}
    )

    return builder.compile()
```

---

## 7. 执行示例

```python
async def run_plan_and_solve(user_input: str) -> str:
    """运行 Plan-and-Solve"""
    graph = build_plan_and_solve_graph()

    result = await graph.ainvoke({
        "user_input": user_input,
        "messages": [HumanMessage(user_input)],
        "mode": "plan",
    })

    return result["step_results"][-1] if result.get("step_results") else ""
```

---

## 8. 依赖处理

```python
# 示例计划
Plan(
    goal="实现用户登录功能",
    steps=[
        PlanStep(step_id="1", description="创建数据库表", action="执行 SQL", depends_on=[]),
        PlanStep(step_id="2", description="编写后端 API", action="调用 write_file", depends_on=["1"]),
        PlanStep(step_id="3", description="编写前端页面", action="调用 write_file", depends_on=["2"]),
    ]
)

# 执行顺序
# step_1 (无依赖) → step_2 (依赖 step_1 完成) → step_3 (依赖 step_2 完成)
```

---

## 9. 相关文档

- [base.md](base.md) - 状态类型定义
- [lead.md](lead.md) - Lead Agent 实现