# Session 会话架构 - SessionContext

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. SessionContext 职责

SessionContext 是会话的核心数据结构，负责：

1. **存储消息历史** - 保留完整的对话历史
2. **容量管理** - 追踪 token 使用，触发压缩
3. **元数据管理** - 存储会话相关信息

---

## 2. 数据结构

```python
@dataclass
class SessionContext:
    """会话上下文"""
    id: str                              # 会话唯一标识
    thread_id: str                       # 线程 ID（用于 Checkpoint）
    messages: list[Message]              # 消息历史
    system_prompt: str                   # 系统提示词
    metadata: dict                       # 额外元数据

    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)

    # 容量管理
    max_tokens: int = 150000             # 最大 token 数
    warn_threshold: float = 0.7          # 警告阈值（70%）
    compact_threshold: float = 0.9       # 压缩阈值（90%）
    keep_recent: int = 5                 # 压缩时保留最近 N 条
```

---

## 3. 容量管理

### 3.1 容量检查

```python
class SessionContext:
    def estimate_tokens(self) -> int:
        """估算当前 token 数"""
        total = 0
        for msg in self.messages:
            total += self._estimate_msg_tokens(msg)
        total += len(self.system_prompt) // 2
        return total

    def _estimate_msg_tokens(self, msg: Message) -> int:
        """估算单条消息 token"""
        # 估算：中文约 2 字符/token，英文约 4 字符/token
        return len(msg.content) // 2

    def get_token_ratio(self) -> float:
        """获取当前使用比例"""
        return self.estimate_tokens() / self.max_tokens
```

### 3.2 阈值判断

```python
class SessionContext:
    def should_warn(self) -> bool:
        """是否需要警告"""
        return self.get_token_ratio() > self.warn_threshold

    def should_compact(self) -> bool:
        """是否需要压缩"""
        return self.get_token_ratio() > self.compact_threshold
```

---

## 4. 上下文压缩

### 4.1 压缩原则

**工具结果不需要特殊处理，统一由上下文压缩处理。**

不需要在工具执行时判断是否持久化，不需要区分显式/隐式调用，不需要额外的文件存储。只需要一个原则：**当上下文超出限制时，统一压缩**。

### 4.2 压缩流程

```
工具执行 → 直接返回结果 → 加入消息列表
                          │
                          ▼
                    检查上下文大小
                          │
                   ┌──────┴──────┐
                   ▼              ▼
               没超限          超限了
                   │              │
                   │              ▼
                   │        统一压缩（LLM 摘要）
                   │              │
                   ▼              ▼
               继续执行      保留摘要 + 最近消息
```

### 4.3 压缩实现

```python
class SessionContext:
    def compact(self) -> str:
        """压缩上下文"""
        if not self.should_compact():
            return ""

        if len(self.messages) <= self.keep_recent:
            return ""

        # 分离旧消息和最近消息
        old_messages = self.messages[:-self.keep_recent]
        recent_messages = self.messages[-self.keep_recent:]

        # LLM 生成摘要
        summary = self._summarize(old_messages)

        # 保留摘要 + 最近消息
        self.messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=f"[之前的对话摘要]\n{summary}",
            )
        ] + recent_messages

        return summary

    def _summarize(self, messages: list[Message]) -> str:
        """LLM 统一摘要"""
        prompt = f"""
        对以下对话进行摘要，保留关键信息：

        1. 关键数据、数字、结论
        2. Agent 的分析和推理
        3. 重要的决策

        忽略：重复内容、中间步骤、原始大文件内容

        对话内容：
        {self._messages_to_text(messages)}
        """

        return llm.invoke(prompt)
```

### 4.4 压缩效果示例

```python
# 压缩前
messages = [
    Message(role="user", content="查看 logs/app.log"),
    Message(role="assistant", content="我来查看..."),
    Message(role="tool", name="read_file", content="[52KB 文件内容...]"),
    Message(role="assistant", content="分析日志..."),
    # ... 更多消息 ...
]

# 压缩后
messages = [
    Message(role="system", content="""
        [之前的对话摘要]
        - 用户查看 logs/app.log（52KB）
        - 发现 156 条 ERROR，主要在 10:23-10:24
        - 原因：数据库连接抖动，已自动恢复
        - Agent 分析了错误模式
    """),
    *recent_messages  # 保留最近 5 条
]
```

### 4.5 LLM 摘要保留什么

| 类型 | 是否保留 | 说明 |
|------|----------|------|
| 关键数据 | ✅ | 数字、统计、结论 |
| Agent 分析 | ✅ | 推理过程和结论 |
| 重要决策 | ✅ | 决策和原因 |
| 原始大文件内容 | ❌ | 被摘要，不保留原始内容 |
| 重复中间步骤 | ❌ | 被压缩 |

---

## 5. 消息管理

### 5.1 添加消息

```python
class SessionContext:
    def add_message(self, message: Message) -> None:
        """添加消息到会话"""
        self.messages.append(message)
        self.last_activity_at = time.time()
```

### 5.2 获取消息

```python
class SessionContext:
    def get_messages_for_llm(self) -> list[Message]:
        """获取发送给 LLM 的消息列表"""
        return self.messages

    def get_recent_messages(self, count: int = 10) -> list[Message]:
        """获取最近 N 条消息"""
        return self.messages[-count:]
```

### 5.3 消息结构

```python
@dataclass
class Message:
    """消息"""
    role: MessageRole
    content: str
    name: Optional[str] = None              # 工具名
    tool_call_id: Optional[str] = None      # 工具调用 ID
    created_at: float = field(default_factory=time.time)


class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
```

---

## 6. 记忆注入

### 6.1 注入时机

| 记忆层 | 注入时机 | 注入位置 |
|--------|----------|----------|
| Preference | 会话开始 | System Prompt |
| Knowledge | 会话开始 + 按需 | System Prompt / 用户消息后 |
| Episodic | 按需检索 | 用户消息后（作为上下文） |

### 6.2 注入追踪

```python
class SessionContext:
    preference_injected: bool = False
    knowledge_injected: bool = False
    skills_injected: bool = False

    def should_inject_preference(self) -> bool:
        return not self.preference_injected

    def mark_preference_injected(self) -> None:
        self.preference_injected = True
```

---

## 7. 会话指标

```python
@dataclass
class SessionMetrics:
    """会话指标"""
    total_turns: int = 0           # 总对话轮数
    total_tasks: int = 0          # 总任务数
    tasks_completed: int = 0      # 已完成任务数
    tasks_failed: int = 0          # 失败任务数
    tools_called: int = 0         # 工具调用总次数
    compact_count: int = 0         # 上下文压缩次数
    session_start: float           # 会话开始时间
```

---

## 8. 序列化

### 8.1 序列化为字典

```python
class SessionContext:
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "messages": [m.to_dict() for m in self.messages],
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "max_tokens": self.max_tokens,
            "warn_threshold": self.warn_threshold,
            "compact_threshold": self.compact_threshold,
            "keep_recent": self.keep_recent,
        }
```

### 8.2 从字典反序列化

```python
    @classmethod
    def from_dict(cls, data: dict) -> SessionContext:
        """从字典反序列化"""
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            thread_id=data.get("thread_id", "default"),
            messages=messages,
            system_prompt=data.get("system_prompt", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            last_activity_at=data.get("last_activity_at", time.time()),
            max_tokens=data.get("max_tokens", 150000),
            warn_threshold=data.get("warn_threshold", 0.7),
            compact_threshold=data.get("compact_threshold", 0.9),
            keep_recent=data.get("keep_recent", 5),
        )
```

---

## 9. 相关文档

- [manager.md](manager.md) - SessionManager 实现
- [checkpoint.md](checkpoint.md) - 会话断点持久化
- [../../memory/index.md](../../memory/index.md) - 记忆系统