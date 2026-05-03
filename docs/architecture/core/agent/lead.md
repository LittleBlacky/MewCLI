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

## 3. 智能分解策略

Lead Agent 使用 LLM 进行任务分解，根据任务特点动态决定：

```python
from core.agent.base import SubTask, DecompositionResult

async def decompose_task(self, task: str) -> list[Task]:
    """智能分解任务（结构化输出 + 验证 + 重试）"""
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            result = await self.llm.with_structured_output(
                DecompositionResult,
                prompt=f"任务: {task}\n\n请判断并分解..."
            )

            # 验证通过，直接使用
            if not result.should_decompose:
                return [Task(description=task)]

            return self.build_tasks(result.subtasks)

        except ValidationError as e:
            if attempt < max_retries - 1:
                logger.warning(f"分解结果验证失败，重试 ({attempt + 1}/{max_retries}): {e}")
                continue
            else:
                logger.warning(f"分解结果验证失败，执行原任务: {e}")
                return [Task(description=task)]
```

**关键设计**：

| 设计点                     | 说明                               |
| -------------------------- | ---------------------------------- |
| **Pydantic 约束**          | 定义输出 schema，LLM 必须严格遵守  |
| **重试机制**               | 最多 3 次，失败后执行原任务         |
| **with_structured_output** | LangChain 原生支持结构化输出       |

---

**分解决策示例**

| 任务类型   | 分解策略                       | 子任务数量  |
| ---------- | ------------------------------ | ----------- |
| "修复 bug" | 分析→复现→修复→测试            | 4           |
| "实现功能" | 分析→设计→实现→测试→集成       | 5           |
| "代码审查" | 按文件分解，每个文件一个子任务 | N（文件数） |
| "重构"     | 分析→规划→执行→验证            | 4           |

---

## 4. Lead Agent 核心方法

```python
from core.agent.base import SubTask, DecompositionResult


class LeadAgent:
    """Lead Agent 实现"""

    async def understand(self, user_input: str) -> str:
        """理解用户意图"""
        # 1. 检索相关记忆
        memories = self.memory.retrieve(user_input)

        # 2. 构建上下文
        context = self.build_context(user_input, memories)

        # 3. 理解意图
        return await self.llm.think(context)

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
                return self.build_tasks(result.subtasks)

            except ValidationError as e:
                if attempt < max_retries - 1:
                    # 未达最大重试次数，尝试重新分解
                    logger.warning(f"分解结果验证失败，重试 ({attempt + 1}/{max_retries}): {e}")
                    continue
                else:
                    # 最后一次失败，执行原任务
                    logger.warning(f"分解结果验证失败，执行原任务: {e}")
                    return [Task(description=task)]

    async def build_tasks(self, subtasks: list[SubTask]) -> list[Task]:
        """根据子任务定义构建任务对象"""
        tasks = []
        for i, st in enumerate(subtasks):
            task = Task(
                id=f"task_{i}",
                description=st.description,
                status=TaskStatus.PENDING,
                created_at=time.time(),
            )
            # 设置依赖关系
            for dep_id in st.dependencies:
                task.children_ids.append(dep_id)
            tasks.append(task)
        return tasks

    async def assign(self, subtasks: list[Task]) -> dict[str, str]:
        """分配任务给 Workers"""
        assignments = {}
        for task in subtasks:
            worker_id = await self.team_manager.assign_task(task)
            assignments[task.id] = worker_id
        return assignments

    async def aggregate(self, results: dict[str, TaskResult]) -> str:
        """汇总 Worker 结果"""
        # 1. 合并所有结果
        combined = "\n".join(r.result for r in results.values() if r.success)

        # 2. 生成最终回复
        prompt = f"合并以下结果并生成最终回复：\n{combined}"
        return await self.llm.think(prompt)
```

---

## 5. LangGraph Node 实现

```python
# Lead Agent Node
async def lead_node(state: AgentState) -> AgentState:
    """Lead Agent 处理节点"""
    messages = state["messages"]
    last_message = messages[-1]

    # 理解任务
    task = await lead.understand(last_message.content)

    # 分解任务
    subtasks = await lead.decompose(task.description)

    # 分配任务
    assignments = await lead.assign(subtasks)

    return {
        **state,
        "task": task,
        "subtasks": subtasks,
    }
```

---

## 6. 与其他模块集成

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

Lead Agent 通过 Team Manager 分配任务给 Workers：

```
Lead Agent ──assign_task()──> Team Manager ──dispatch──> Workers
                           │
                           <──on_task_completed()──
```

---

## 7. 关键设计决策

| 决策项        | 选择     | 说明                   |
| ------------- | -------- | ---------------------- |
| 使用 LLM 分解 | 动态决定 | 根据任务特点自适应分解 |
| Lead 负责汇总 | 集中管理 | 统一生成最终回复       |
| 与 Skill 集成 | 技能匹配 | 任务开始时匹配相关技能 |

---

## 8. 相关文档

- [base.md](base.md) - 核心类型定义
- [worker.md](worker.md) - Worker Agent 实现
- [../team/index.md](../team/index.md) - Team 协作架构
