# MiniCode 架构设计文档 - Checkpoint 持久化

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 设计目标

**Checkpoint 持久化** - 支持状态保存和恢复，实现断点续连。

### 1.1 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **持久化** | 支持状态保存 | 可靠性 |
| **增量保存** | 只保存变更 | 性能 |
| **可追溯** | 支持版本回溯 | 调试 |

### 1.2 为什么这样设计

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| Checkpoint 持久化 | 支持断点续连 | 系统可靠性 |
| 父子链 | 支持版本回溯 | 调试 |
| 异步保存 | 不阻塞主流程 | 性能 |

---

## 2. 模块结构

```
infra/checkpoint/
├── __init__.py          # 导出公共类型
├── store.py             # CheckpointStore 存储
├── manager.py           # CheckpointManager 管理器
└── types.py            # Checkpoint 类型定义
```

---

## 3. Checkpoint 定义

### 3.1 核心类型

```python
@dataclass
class Checkpoint:
    """断点数据"""
    state: dict                        # 状态数据
    checkpoint_id: str                 # 断点 ID
    parent_id: Optional[str] = None    # 父断点 ID
    metadata: dict = field(default_factory=dict)  # 元数据
    created_at: float = field(default_factory=time.time)  # 创建时间

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "state": self.state,
            "checkpoint_id": self.checkpoint_id,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """从字典反序列化"""
        return cls(
            state=data["state"],
            checkpoint_id=data["checkpoint_id"],
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
        )
```

### 3.2 Checkpoint 元数据

```python
@dataclass
class CheckpointMetadata:
    """断点元数据"""
    thread_id: str                     # 线程 ID
    created_by: str                    # 创建者
    checkpoint_type: str               # 断点类型（auto/manual）
    state_summary: str                 # 状态摘要
    tags: list[str] = field(default_factory=list)  # 标签
```

---

## 4. CheckpointStore 设计

### 4.1 存储接口

```python
class CheckpointStore:
    """断点存储"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: Checkpoint) -> None:
        """保存断点"""
        filepath = self.storage_dir / f"checkpoint_{checkpoint.checkpoint_id}.json"
        filepath.write_text(json.dumps(checkpoint.to_dict(), indent=2))

    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """加载断点"""
        filepath = self.storage_dir / f"checkpoint_{checkpoint_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            return Checkpoint.from_dict(data)
        return None

    def list_checkpoints(self) -> list[str]:
        """列出所有断点"""
        return [f.stem.replace("checkpoint_", "") for f in self.storage_dir.glob("checkpoint_*.json")]

    def delete(self, checkpoint_id: str) -> bool:
        """删除断点"""
        filepath = self.storage_dir / f"checkpoint_{checkpoint_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def delete_all(self) -> None:
        """删除所有断点"""
        for f in self.storage_dir.glob("checkpoint_*.json"):
            f.unlink()
```

### 4.2 SQLite 存储（可选）

```python
class SQLiteCheckpointStore(CheckpointStore):
    """SQLite 实现的断点存储"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                parent_id TEXT,
                state TEXT,
                metadata TEXT,
                created_at REAL
            )
        """)
        conn.close()

    def save(self, checkpoint: Checkpoint) -> None:
        """保存断点到数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO checkpoints
            (checkpoint_id, parent_id, state, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            checkpoint.checkpoint_id,
            checkpoint.parent_id,
            json.dumps(checkpoint.state),
            json.dumps(checkpoint.metadata),
            checkpoint.created_at,
        ))
        conn.commit()
        conn.close()
```

---

## 5. CheckpointManager 设计

### 5.1 管理器接口

```python
class CheckpointManager:
    """断点管理器"""

    def __init__(self, store: CheckpointStore):
        self.store = store
        self._current_checkpoint: Optional[Checkpoint] = None

    async def save_checkpoint(
        self,
        state: dict,
        thread_id: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """保存断点"""
        checkpoint_id = f"{thread_id}_{int(time.time() * 1000)}"

        checkpoint = Checkpoint(
            state=state,
            checkpoint_id=checkpoint_id,
            parent_id=self._current_checkpoint.checkpoint_id if self._current_checkpoint else None,
            metadata=metadata or {},
        )

        self.store.save(checkpoint)
        self._current_checkpoint = checkpoint

        return checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """加载断点"""
        checkpoint = self.store.load(checkpoint_id)
        if checkpoint:
            self._current_checkpoint = checkpoint
            return checkpoint.state
        return None

    def get_latest(self, thread_id: str) -> Optional[dict]:
        """获取最新断点"""
        checkpoints = self.store.list_checkpoints()
        thread_checkpoints = [c for c in checkpoints if c.startswith(thread_id)]
        if thread_checkpoints:
            # 按时间戳排序，取最新
            latest_id = sorted(thread_checkpoints)[-1]
            return self.store.load(latest_id).state if latest_id else None
        return None

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除断点"""
        return self.store.delete(checkpoint_id)
```

### 5.2 自动保存策略

```python
class AutoSaveStrategy:
    """自动保存策略"""

    def __init__(
        self,
        manager: CheckpointManager,
        interval: float = 60.0,      # 间隔（秒）
        on_state_change: bool = True, # 状态变化时保存
    ):
        self.manager = manager
        self.interval = interval
        self.on_state_change = on_state_change
        self._last_save = 0.0
        self._last_state: Optional[dict] = None

    async def maybe_save(
        self,
        state: dict,
        thread_id: str,
        force: bool = False,
    ) -> Optional[str]:
        """可能保存断点"""
        current_time = time.time()

        # 检查是否需要保存
        should_save = (
            force or
            (current_time - self._last_save >= self.interval) or
            (self.on_state_change and state != self._last_state)
        )

        if should_save:
            checkpoint_id = await self.manager.save_checkpoint(
                state, thread_id, metadata={"auto": True}
            )
            self._last_save = current_time
            self._last_state = state.copy()
            return checkpoint_id

        return None
```

---

## 6. Checkpoint 策略

### 6.1 保存策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **定时保存** | 每 N 秒保存一次 | 长时间任务 |
| **状态变化保存** | 状态变化时保存 | 重要操作 |
| **手动保存** | 用户触发保存 | 关键节点 |
| **自动 + 手动** | 综合策略 | 一般场景 |

### 6.2 恢复策略

| 策略 | 说明 | 实现 |
|------|------|------|
| **最新恢复** | 恢复到最近断点 | 直接加载最新 |
| **指定恢复** | 恢复到指定断点 | 按 ID 加载 |
| **父子链** | 沿父子链回溯 | 调试 |

---

## 7. 与 LangGraph 集成

### 7.1 LangGraph Checkpoint

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

def create_checkpoint_graph(
    state_schema: Type,
    storage_type: str = "memory",
) -> CompiledGraph:
    """创建带 Checkpoint 的图"""

    # 选择存储后端
    if storage_type == "memory":
        checkpointer = MemorySaver()
    elif storage_type == "sqlite":
        checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
    else:
        checkpointer = None

    graph = StateGraph(state_schema)
    # ... 添加节点和边 ...

    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
```

### 7.2 带 Checkpoint 的执行

```python
# 带 Checkpoint 的执行
config = {"configurable": {"thread_id": "session_123"}}

# 首次执行
result = graph.invoke(initial_state, config)

# 恢复执行（从断点继续）
result = graph.invoke(None, config)  # 传入 None，从断点恢复

# 指定断点恢复
config = {"configurable": {"thread_id": "session_123", "checkpoint_id": "ckpt_xxx"}}
result = graph.invoke(None, config)
```

---

## 8. 实现要点

1. **异步保存**：不阻塞主流程
2. **状态变化检测**：避免无意义保存
3. **存储压缩**：定期清理旧断点
4. **错误处理**：保存失败不影响主流程

---

## 9. 参考资料

- [LangGraph Checkpointing](https://langchain-ai.github.io/langgraph/concepts/checkpointing/)
- [LangGraph Persistence](https://python.langchain.com/docs/how_to/persistence/)