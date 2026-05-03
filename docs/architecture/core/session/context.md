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
4. **记忆注入** - 管理记忆注入状态

---

## 2. SessionContext 结构

```python
@dataclass
class SessionContext:
    """会话上下文"""
    id: str                          # 会话唯一标识
    thread_id: str                   # 线程 ID（用于 Checkpoint）
    created_at: float                 # 创建时间
    last_activity_at: float           # 最后活动时间
    messages: list[Message]          # 消息历史
    system_prompt: str                # 系统提示词
    metadata: dict                    # 额外元数据

    # 容量管理
    max_messages: int = 50           # 最大消息数
    max_tokens: int = 150000        # 最大 token 数
    compact_threshold: float = 0.7    # 压缩阈值（70%）

    # 记忆注入状态
    preference_injected: bool = False
    knowledge_injected: bool = False
    skills_injected: bool = False
```

---

## 3. 容量管理方法

```python
class SessionContext:
    def estimate_tokens(self) -> int:
        """估算当前 token 数"""
        total = 0
        for msg in self.messages:
            # 估算：中文约 2 字符/token，英文约 4 字符/token
            total += len(msg.content) // 2
        total += len(self.system_prompt) // 2
        return total

    def get_token_ratio(self) -> float:
        """获取当前使用比例"""
        return self.estimate_tokens() / self.max_tokens

    def should_warn(self) -> bool:
        """是否需要警告"""
        return self.get_token_ratio() > self.compact_threshold

    def should_compact(self) -> bool:
        """是否需要压缩"""
        return self.get_token_ratio() > 0.9
```

---

## 4. 上下文压缩

### 4.1 压缩触发条件

```python
class SessionContext:
    def should_compact(self) -> bool:
        """判断是否需要压缩"""
        # 条件1: 消息数量超过阈值
        if len(self.messages) > self.max_messages:
            return True

        # 条件2: Token 使用超过阈值
        if self.get_token_ratio() > self.compact_threshold:
            return True

        return False
```

### 4.2 压缩策略

```python
class SessionContext:
    def compact(self, keep_recent: int = 5) -> str:
        """压缩上下文，保留最近 N 条消息"""
        if len(self.messages) <= keep_recent:
            return ""

        # 生成摘要
        summary = self._summarize_old_messages(
            self.messages[:-keep_recent]
        )

        # 保留最近的消息 + 摘要
        self.messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=f"[之前的对话摘要]\n{summary}",
            )
        ] + self.messages[-keep_recent:]

        return summary

    def _summarize_old_messages(self, messages: list[Message]) -> str:
        """生成旧消息的摘要"""
        # 使用 LLM 生成摘要
        # 简化版本：返回消息数量和主题
        return f"（省略了 {len(messages)} 条消息）"
```

---

## 5. 消息管理

### 5.1 添加消息

```python
class SessionContext:
    def add_message(self, message: Message) -> None:
        """添加消息到会话"""
        self.messages.append(message)
        self.last_activity_at = datetime.now().timestamp()
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

    def get_messages_since(self, timestamp: float) -> list[Message]:
        """获取指定时间之后的消息"""
        return [m for m in self.messages if m.created_at >= timestamp]
```

---

## 6. 记忆注入管理

### 6.1 注入状态追踪

```python
class SessionContext:
    def mark_preference_injected(self) -> None:
        """标记偏好已注入"""
        self.preference_injected = True

    def mark_knowledge_injected(self) -> None:
        """标记知识已注入"""
        self.knowledge_injected = True

    def mark_skills_injected(self) -> None:
        """标记技能已注入"""
        self.skills_injected = True

    def should_inject_preference(self) -> bool:
        """是否需要注入偏好"""
        return not self.preference_injected

    def should_inject_knowledge(self) -> bool:
        """是否需要注入知识"""
        return not self.knowledge_injected
```

### 6.2 注入流程

```
                    用户输入
                         │
                         ▼
              ┌─────────────────────┐
              │  检索相关记忆       │
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    Preference      Knowledge        Skill
          │              │              │
          ▼              ▼              ▼
    已注入？         已注入？        已注入？
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  注入到 System Prompt│
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  发送请求给 LLM     │
              └─────────────────────┘
```

---

## 7. 会话配置

```python
@dataclass
class SessionConfig:
    """会话配置"""
    compact_threshold: int = 50           # 消息数阈值
    compact_keep_recent: int = 5          # 压缩时保留最近 N 条
    memory_on_task_complete: bool = True  # 任务完成时自动保存记忆
    reflect_on_idle: bool = True          # 空闲时反思
    reflect_interval: int = 10            # 反思间隔（轮数）
    context_limit: int = 50000            # 字符数限制
    max_output_chars: int = 15000         # 长输出阈值
    compact_ratio: float = 0.7            # 容量阈值
```

---

## 8. 会话指标

```python
@dataclass
class SessionMetrics:
    """会话指标"""
    total_turns: int = 0          # 总对话轮数
    total_tasks: int = 0         # 总任务数
    tasks_completed: int = 0      # 已完成任务数
    tasks_failed: int = 0         # 失败任务数
    tools_called: int = 0        # 工具调用总次数
    compact_count: int = 0        # 上下文压缩次数
    output_saved_count: int = 0   # 长输出保存次数
    session_start: float          # 会话开始时间
```

---

## 9. 序列化

### 9.1 序列化为字典

```python
class SessionContext:
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "messages": [m.to_dict() for m in self.messages],
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
            "compact_threshold": self.compact_threshold,
        }
```

### 9.2 从字典反序列化

```python
    @classmethod
    def from_dict(cls, data: dict) -> SessionContext:
        """从字典反序列化"""
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            thread_id=data.get("thread_id", "default"),
            created_at=data.get("created_at", datetime.now().timestamp()),
            last_activity_at=data.get("last_activity_at", datetime.now().timestamp()),
            messages=messages,
            system_prompt=data.get("system_prompt", ""),
            metadata=data.get("metadata", {}),
            max_messages=data.get("max_messages", 50),
            max_tokens=data.get("max_tokens", 150000),
            compact_threshold=data.get("compact_threshold", 0.7),
        )
```

---

## 10. 相关文档

- [manager.md](manager.md) - SessionManager 实现
- [checkpoint.md](checkpoint.md) - 会话断点持久化
- [../../memory/index.md](../../memory/index.md) - 记忆系统