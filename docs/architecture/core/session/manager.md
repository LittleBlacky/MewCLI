# Session 会话架构 - SessionManager

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. SessionManager 职责

SessionManager 负责会话的生命周期管理：

1. **会话创建/销毁** - 创建新会话，销毁旧会话
2. **会话切换** - 管理当前活跃会话
3. **会话持久化** - 保存和恢复会话
4. **会话列表** - 列出和管理所有会话

---

## 2. SessionManager 架构

```
SessionManager
    │
    ├── 会话存储
    │   ├── _sessions: dict[str, SessionContext]
    │   └── _current_session: Optional[SessionContext]
    │
    ├── 存储配置
    │   └── storage_dir: Path
    │
    └── 配置
        └── config: SessionConfig
```

---

## 3. SessionManager 核心方法

```python
class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.config = config or SessionConfig()
        self.storage_dir = storage_dir or Path.home() / ".minicode" / "sessions"
        self._sessions: dict[str, SessionContext] = {}
        self._current_session: Optional[SessionContext] = None

    def create_session(
        self,
        thread_id: str = "default",
        system_prompt: str = "",
        metadata: Optional[dict] = None,
    ) -> SessionContext:
        """创建新会话"""

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话"""

    def get_current_session(self) -> Optional[SessionContext]:
        """获取当前会话"""

    def set_current_session(self, session_id: str) -> bool:
        """设置当前会话"""

    def end_session(self, session_id: str, save: bool = True) -> None:
        """结束会话"""

    def _save_session(self, session: SessionContext) -> None:
        """保存会话到磁盘"""

    def load_session(self, session_id: str) -> Optional[SessionContext]:
        """从磁盘加载会话"""

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""

    def get_or_create_current(
        self,
        thread_id: str = "default",
        system_prompt: str = "",
    ) -> SessionContext:
        """获取或创建当前会话"""
```

---

## 4. 会话生命周期

### 4.1 生命周期状态

```
                    create_session()
                         │
                         ▼
                      CREATED
                         │
                         ▼
                      ACTIVE
         ┌──────────────┼──────────────┐
         │              │              │
   add_message()   compact()     end_session()
         │              │              │
         ▼              ▼              ▼
      ACTIVE        COMPACTED       ENDED
         │              │              │
         │              │              ▼
         │              │           SAVED
         │              │              │
         │              ▼         (to disk)
         │           ACTIVE
         │              │
         └──────────────┘
```

### 4.2 会话状态定义

```python
class SessionState(Enum):
    """会话状态"""
    CREATED = "created"     # 已创建
    ACTIVE = "active"       # 活跃中
    COMPACTED = "compacted" # 压缩中
    ENDED = "ended"         # 已结束
    SAVED = "saved"         # 已保存
```

---

## 5. 会话持久化

### 5.1 保存会话

```python
class SessionManager:
    def _save_session(self, session: SessionContext) -> None:
        """保存会话到磁盘"""
        filepath = self.storage_dir / f"session_{session.id}.json"
        data = session.to_dict()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

### 5.2 加载会话

```python
class SessionManager:
    def load_session(self, session_id: str) -> Optional[SessionContext]:
        """从磁盘加载会话"""
        filepath = self.storage_dir / f"session_{session_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            session = SessionContext.from_dict(data)
            self._sessions[session_id] = session
            return session
        return None
```

---

## 6. 多会话管理

### 6.1 会话切换

```python
class SessionManager:
    def switch_session(self, session_id: str) -> bool:
        """切换到另一个会话"""
        if session_id in self._sessions:
            self._current_session = self._sessions[session_id]
            return True
        return False

    def create_new_session(self) -> SessionContext:
        """创建新会话并切换"""
        session = self.create_session()
        self._current_session = session
        return session
```

### 6.2 会话隔离与上下文隔离

**会话隔离**：每个 SessionContext 独立存储，互不影响：

```
SessionManager
    │
    ├── Session A
    │   └── messages: [M1, M2, M3]
    │
    ├── Session B
    │   └── messages: [M1, M2]
    │
    └── Session C
        └── messages: [M1, M2, M3, M4, M5]
```

**Lead/Worker 上下文隔离**：Worker 使用独立的 SubtaskContext，防止相互干扰：

| Agent 类型 | Context 类型 | 说明 |
| ---------- | ------------ | ---- |
| Lead Agent | SessionContext | 完整上下文，含所有消息和状态 |
| Worker Agent | SubtaskContext | 子任务上下文，仅包含相关消息 |

---

## 7. 与其他模块集成

### 7.1 与 Agent 层集成

```python
class LeadAgent:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def handle_user_input(self, user_input: str) -> str:
        session = self.session_manager.get_current_session()

        # 1. 添加用户消息
        session.add_message(Message(
            role=MessageRole.USER,
            content=user_input,
        ))

        # 2. 检查是否需要压缩
        if session.should_compact():
            summary = session.compact()

        # 3. 处理请求
        response = await self.process(session)

        # 4. 添加响应消息
        session.add_message(Message(
            role=MessageRole.ASSISTANT,
            content=response,
        ))

        return response
```

### 7.2 与 Evolution 层集成

```python
class SessionManager:
    def on_session_end(self, session_id: str) -> None:
        """会话结束时调用"""
        session = self.get_session(session_id)
        if not session:
            return

        # 1. 更新指标
        metrics = session.metadata.get("metrics", SessionMetrics())

        # 2. 通知 Evolution Engine
        evolution_engine.record_session(session)

        # 3. 保存会话
        self.end_session(session_id, save=True)
```

---

## 8. 相关文档

- [context.md](context.md) - SessionContext 实现
- [checkpoint.md](checkpoint.md) - 会话断点持久化
- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构