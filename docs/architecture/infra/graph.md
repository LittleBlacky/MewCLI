# MiniCode 架构设计文档 - Graph 状态图架构

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 设计目标

**Graph 状态图** - 基于 LangGraph 的状态机封装，简化状态图构建。

### 1.1 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **链式调用** | Builder 模式链式调用 | 简化图构建 |
| **类型安全** | 使用 TypedDict 定义状态 | 类型检查 |
| **可扩展** | 支持自定义节点和边 | 灵活定制 |

### 1.2 为什么这样设计

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| GraphBuilder 封装 | 简化 LangGraph 使用 | 开发效率 |
| TypedDict 状态 | 提供类型提示 | IDE 支持 |
| 条件边支持 | 支持复杂流程控制 | 功能强大 |

---

## 2. 模块结构

```
infra/graph/
├── __init__.py          # 导出公共类型
├── builder.py           # GraphBuilder 状态图构建器
└── state.py             # Graph State 定义
```

---

## 3. GraphBuilder 设计

### 3.1 核心接口

```python
class GraphBuilder:
    """LangGraph 状态图构建器"""

    def __init__(self, state_schema: Type):
        self.schema = state_schema
        self._graph = StateGraph(state_schema)
        self._nodes: dict[str, Callable] = {}
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: dict[str, tuple[Callable, list[str]]] = {}

    def add_node(self, name: str, fn: Callable) -> "GraphBuilder":
        """添加节点"""
        self._nodes[name] = fn
        self._graph.add_node(name, fn)
        return self

    def add_edge(self, from_node: str, to_node: str) -> "GraphBuilder":
        """添加边"""
        self._edges.append((from_node, to_node))
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        condition: Callable,
        mapping: dict[str, str],
    ) -> "GraphBuilder":
        """添加条件边"""
        self._conditional_edges[from_node] = (condition, list(mapping.keys))
        return self

    def set_entry_point(self, node: str) -> "GraphBuilder":
        """设置入口节点"""
        self._graph.set_entry_point(node)
        return self

    def set_finish_point(self, node: Union[str, type[END]] = END) -> "GraphBuilder":
        """设置结束节点"""
        if node == END:
            self._graph.set_finish_point(END)
        else:
            self._graph.add_edge(node, END)
        return self

    def compile(self) -> Any:
        """编译图"""
        # 添加边
        for from_node, to_node in self._edges:
            self._graph.add_edge(from_node, to_node)

        # 添加条件边
        for from_node, (condition, path_mapping) in self._conditional_edges.items():
            self._graph.add_conditional_edges(
                from_node,
                condition,
                path_mapping,
            )

        return self._graph.compile()
```

### 3.2 使用示例

```python
from infra.graph import GraphBuilder

# 定义状态
class MyState(TypedDict):
    messages: Annotated[list, add_messages]
    count: int

# 构建图
graph = (
    GraphBuilder(MyState)
    .add_node("process", process_node)
    .add_node("respond", respond_node)
    .add_edge("process", "respond")
    .set_entry_point("process")
    .set_finish_point()
    .compile()
)
```

---

## 4. Graph State 定义

### 4.1 基础状态

```python
from typing import TypedDict
from typing_extensions import Annotated
from langgraph.graph import add_messages


class GraphState(TypedDict):
    """综合图状态"""
    messages: Annotated[list, add_messages]  # 消息列表（自动合并）
    tool_messages: list                      # 工具消息
    last_summary: str                        # 最后摘要
    mode: str                                # 运行模式
    task_count: int                           # 任务计数
    permission_rules: list                   # 权限规则
    consecutive_denials: int                 # 连续拒绝次数


class GraphTaskState(TypedDict):
    """任务图状态"""
    task_items: list[dict]        # 任务列表
    pending_tasks: list[dict]     # 待处理任务


class GraphExecutionState(TypedDict):
    """执行图状态"""
    evaluation_score: float        # 评估分数
    execution_steps: list[str]    # 执行步骤
    error_recovery_count: int     # 错误恢复次数
```

### 4.2 状态初始化

```python
def create_initial_state(messages: Optional[list] = None, mode: str = "default") -> dict:
    """创建初始图状态"""
    return {
        "messages": messages or [],
        "tool_messages": [],
        "last_summary": "",
        "mode": mode,
        "task_count": 0,
        "permission_rules": [],
        "consecutive_denials": 0,
    }
```

---

## 5. 与 LangGraph 深度集成

### 5.1 LangGraph Checkpoint

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

def create_checkpoint_graph(state_schema: Type) -> CompiledGraph:
    """创建带 Checkpoint 的图"""
    checkpointer = MemorySaver()

    graph = StateGraph(state_schema)
    # ... 添加节点和边 ...

    return graph.compile(checkpointer=checkpointer)
```

### 5.2 带 Checkpoint 的 Graph

```python
# 带 Checkpoint 的执行
config = {"configurable": {"thread_id": "session_123"}}

# 首次执行
result = graph.invoke(initial_state, config)

# 恢复执行
result = graph.invoke(None, config)  # 从断点恢复
```

---

## 6. 实现要点

1. **延迟初始化**：客户端延迟初始化，避免启动开销
2. **线程安全**：使用锁保护共享状态
3. **错误处理**：优雅处理 LangGraph 异常

---

## 7. 参考资料

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [StateGraph API](https://python.langchain.com/docs/concepts/ LangGraph/#stategraph)