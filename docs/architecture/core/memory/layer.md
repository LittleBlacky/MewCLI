# Memory 记忆架构 - 记忆层整合

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. MemoryLayer 职责

MemoryLayer 是三层记忆的统一入口：

1. **统一检索** - 提供统一的检索接口
2. **缓存管理** - 减少重复检索
3. **记忆注入** - 自动注入相关记忆到上下文

---

## 2. MemoryLayer 实现

```python
class MemoryLayer:
    """记忆层"""

    def __init__(self, thread_id: str = "default"):
        self.thread_id = thread_id
        self.preference = PreferenceMemory()
        self.knowledge = KnowledgeMemory()
        self.episodic = EpisodicMemory()
        self.dream = DreamConsolidator()

        # 检索缓存
        self._cache: dict[str, str] = {}
        self._cache_time: float = 0
        self._cache_ttl = 180  # 3 分钟
```

---

## 3. 检索流程

```
                    用户输入
                         │
                         ▼
              ┌─────────────────────────┐
              │   检查缓存             │
              └───────────┬─────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
            命中                    未命中
              │                       │
              │                       ▼
              │           ┌─────────────────────────┐
              │           │   检索 Preference        │
              │           └───────────┬─────────────┘
              │                       │
              │           ┌───────────┴───────────┐
              │           │                       │
              │           ▼                       ▼
              │       有结果                  无结果
              │           │                       │
              │           ▼                       ▼
              │       ┌────────────┐     ┌─────────────────────────┐
              │       │   更新缓存  │     │   检索 Knowledge         │
              │       └────────────┘     └───────────┬─────────────┘
              │                                       │
              │           ┌───────────┴───────────┐    │
              │           │                       │    │
              │           ▼                       ▼    │
              │       有结果                  无结果   │
              │           │                       │    │
              │           ▼                       ▼    │
              │       ┌────────────┐     ┌─────────────────────────┐
              │       │   更新缓存  │     │   检索 Episodic        │
              │       └────────────┘     └───────────┬─────────────┘
              │                                       │
              │                                       ▼
              │                               ┌─────────────────────────┐
              │                               │   返回空结果           │
              │                               └─────────────────────────┘
              │
              ▼
        ┌─────────────────────────┐
        │   返回缓存结果         │
        └─────────────────────────┘
```

---

## 4. 注入策略

```python
class MemoryLayer:
    def build_static_prompt(self) -> str:
        """构建静态记忆部分"""
        parts = []

        # 偏好
        preferences = self.preference.get_preferences()
        if preferences:
            parts.append(preferences)

        # 知识
        project = self.knowledge.get_project_knowledge()
        if project:
            parts.append(project)

        return "\n".join(parts)

    def retrieve_episodic(self, query: str) -> str:
        """检索事件记忆"""
        if not self.should_retrieve_episodic(query):
            return ""

        entries = self.episodic.search(query, limit=3)
        if not entries:
            return ""

        parts = ["\n\n## 相关经验"]
        for e in entries:
            parts.append(f"### [{e.memory_type}] {e.name}")
            parts.append(e.content[:300])

        return "\n".join(parts)
```

---

## 5. 注入时机

| 记忆层 | 注入时机 | 注入位置 |
|--------|----------|----------|
| Preference | 会话开始 | System Prompt |
| Knowledge | 会话开始 + 按需 | System Prompt / 用户消息后 |
| Episodic | 按需检索 | 用户消息后（作为上下文） |

---

## 6. 事件记忆整合

```python
class MemoryLayer:
    def consolidate(self) -> dict:
        """整合事件记忆"""
        # 按类型分组
        by_type: dict[str, list] = {}
        for entry in self.episodic._index.values():
            if entry.memory_type not in by_type:
                by_type[entry.memory_type] = []
            by_type[entry.memory_type].append(entry)

        # 每类只保留最新 20 条
        for mem_type, entries in by_type.items():
            if len(entries) > 20:
                entries.sort(key=lambda e: e.last_accessed, reverse=True)
                for entry in entries[20:]:
                    self._delete_episode(entry.name)

        return {
            "action": "consolidate",
            "remaining": len(self.episodic._index),
        }
```

---

## 7. Session 记忆

### 7.1 SessionContext 结构

```python
@dataclass
class SessionContext:
    """会话上下文 - 动态记忆"""
    thread_id: str
    created_at: float = field(default_factory=time.time)
    task_id: str = ""
    task_description: str = ""
    recent_decisions: list[str] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    completed_items: list[str] = field(default_factory=list)
    session_summary: str = ""
```

### 7.2 会话记忆管理

```python
class SessionMemory:
    """会话记忆管理"""

    def __init__(self, thread_id: str = "default"):
        self.thread_id = thread_id
        self.context_file = SESSION_DIR / f"session_{thread_id}.json"
        self.context: SessionContext = self._load()

    def set_task(self, task_id: str, description: str) -> None:
        """设置当前任务"""

    def add_decision(self, decision: str) -> None:
        """记录决策"""

    def add_pending(self, item: str) -> None:
        """添加待办"""

    def complete_pending(self, item: str) -> None:
        """完成待办"""

    def update_summary(self, summary: str) -> None:
        """更新会话摘要"""

    def get_current_context(self) -> str:
        """获取当前会话上下文"""
```

---

## 8. 与其他模块集成

### 8.1 与 Lead Agent 集成

```python
class LeadAgent:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def understand(self, user_input: str) -> str:
        # 1. 检索相关记忆
        memories = self.memory.retrieve(user_input)

        # 2. 构建上下文
        context = self.build_context(user_input, memories)

        # 3. 理解意图
        return await self.llm.think(context)

    def build_context(self, user_input: str, memories: dict) -> str:
        """构建包含记忆的上下文"""
        parts = [f"用户输入: {user_input}"]

        # 添加记忆
        if memories.get("preference"):
            parts.append(f"\n\n# 用户偏好\n{memories['preference']}")

        if memories.get("knowledge"):
            parts.append(f"\n\n# 项目知识\n{memories['knowledge']}")

        if memories.get("episodic"):
            parts.append(f"\n\n# 相关经验\n{memories['episodic']}")

        return "\n\n".join(parts)
```

### 8.2 与 Evolution 集成

```python
class EvolutionEngine:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def on_skill_created(self, skill: Skill) -> None:
        """技能创建时更新记忆"""
        self.memory.skill.save_skill(
            name=skill.name,
            description=skill.description,
            code=skill.code,
        )

    async def update_preferences(self, preferences: list[Preference]) -> None:
        """更新偏好"""
        for pref in preferences:
            self.memory.preference.save_preference(pref.key, pref.value)
```

---

## 9. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [episodic.md](episodic.md) - Episodic 事件层
- [dream.md](dream.md) - Dream 梦境整合