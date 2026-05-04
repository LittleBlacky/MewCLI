# Memory 记忆架构 - 记忆层整合

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. MemoryLayer 职责

MemoryLayer 是三层记忆的统一入口：

1. **统一操作** - 提供一致的 CRUD 接口
2. **LLM 检索** - 语义理解用户意图，智能匹配
3. **记忆注入** - 自动注入相关记忆到上下文

---

## 2. MemoryLayer 实现

```python
class MemoryLayer:
    """统一记忆层"""

    def __init__(self, llm, storage_dir: Path):
        self.llm = llm
        self.preference = PreferenceMemory(storage_dir)
        self.knowledge = KnowledgeMemory(storage_dir)
        self.episodic = EpisodicMemory(storage_dir, llm)
```

---

## 3. 操作总览

### 3.1 Preference 操作

```python
class MemoryLayer:
    # 存入
    def save_preference(self, key: str, value: str) -> None:
        self.preference.save(key, value)

    # 读取单个
    def get_preference(self, key: str) -> Optional[str]:
        return self.preference.get(key)

    # 读取全部
    def get_all_preferences(self) -> str:
        return self.preference.get_all()

    # 更新
    def update_preference(self, key: str, value: str) -> None:
        self.preference.update(key, value)

    # 删除
    def delete_preference(self, key: str) -> None:
        self.preference.delete(key)

    # 列表
    def list_preferences(self) -> list[dict]:
        return self.preference.list_all()
```

### 3.2 Knowledge 操作

```python
class MemoryLayer:
    # 存入
    def save_knowledge(self, key: str, value: str) -> None:
        self.knowledge.save(key, value)

    # 读取单个
    def get_knowledge(self, key: str) -> Optional[str]:
        return self.knowledge.get(key)

    # 读取全部
    def get_all_knowledge(self) -> str:
        return self.knowledge.get_all()

    # 读取项目知识
    def get_project_knowledge(self) -> str:
        return self.knowledge.get_project_knowledge()

    # 更新
    def update_knowledge(self, key: str, value: str) -> None:
        self.knowledge.update(key, value)

    # 删除
    def delete_knowledge(self, key: str) -> None:
        self.knowledge.delete(key)

    # 列表
    def list_knowledge(self) -> list[dict]:
        return self.knowledge.list_all()
```

### 3.3 Episodic 操作

```python
class MemoryLayer:
    # 存入
    async def save_episode(self, name: str, content: str, memory_type: str) -> None:
        self.episodic.save(name, content, memory_type)

    # 读取单个
    def get_episode(self, name: str) -> Optional[MemoryEntry]:
        return self.episodic.get(name)

    # 读取全部
    def get_all_episodes(self) -> list[MemoryEntry]:
        return self.episodic.get_all()

    # 删除
    def delete_episode(self, name: str) -> None:
        self.episodic.delete(name)

    # LLM 检索
    async def search_episodes(self, query: str) -> str:
        return await self.episodic.search(query)

    # 整合（Dream 调用）
    def consolidate_episodes(self) -> dict:
        return self.episodic.consolidate()
```

---

## 4. LLM 统一检索

三层记忆统一使用 LLM 检索，语义理解用户意图。

### 4.1 检索流程

```
用户输入
    │
    ▼
Preference → 直接获取（量少）
    │
Knowledge → 直接获取（量少）
    │
Episodic → LLM 语义检索（量大）
    │
    ▼
返回相关记忆
```

### 4.2 实现

```python
async def retrieve(self, query: str) -> dict[str, str]:
    """LLM 统一检索"""

    # 1. Preference - 直接获取（量少）
    pref = self.preference.get_all()

    # 2. Knowledge - 直接获取（量少）
    know = self.knowledge.get_all()

    # 3. Episodic - LLM 检索（量大且需要语义理解）
    episodic = await self.episodic.search(query)

    return {
        "preference": pref,
        "knowledge": know,
        "episodic": episodic
    }
```

### 4.3 为什么 Preference/Knowledge 不需要 LLM 检索

| 记忆层 | 特点 | 检索方式 |
|--------|------|----------|
| Preference | 数量少、稳定（几十条） | 直接获取 |
| Knowledge | 数量少、稳定 | 直接获取 |
| Episodic | 数量会增长、需要语义理解 | LLM 检索 |

---

## 5. 构建上下文

将记忆注入到上下文中，供 Agent 使用。

```python
async def build_context(self, user_input: str) -> str:
    """构建包含记忆的上下文"""

    # LLM 统一检索
    memories = await self.retrieve(user_input)

    # 构建上下文
    parts = [f"# 用户输入\n{user_input}"]

    if memories.get("preference") and memories["preference"].strip():
        parts.append(f"\n## 用户偏好\n{memories['preference']}")

    if memories.get("knowledge") and memories["knowledge"].strip():
        parts.append(f"\n## 项目知识\n{memories['knowledge']}")

    if memories.get("episodic") and "无相关记忆" not in memories["episodic"]:
        parts.append(f"\n## 相关经验\n{memories['episodic']}")

    return "\n\n".join(parts)
```

---

## 6. 注入时机

| 记忆层 | 注入时机 | 注入位置 |
|--------|----------|----------|
| Preference | 会话开始 | System Prompt |
| Knowledge | 会话开始 | System Prompt |
| Episodic | LLM 判断相关时 | 用户消息后 |

---

## 7. Session 记忆

SessionContext 是当前会话的动态记忆，不属于持久化存储。

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

### 7.2 操作

```python
class SessionContext:
    def set_task(self, task_id: str, description: str) -> None: ...
    def add_decision(self, decision: str) -> None: ...
    def add_pending(self, item: str) -> None: ...
    def complete_pending(self, item: str) -> None: ...
    def update_summary(self, summary: str) -> None: ...
    def get_context(self) -> str: ...
```

---

## 8. 与其他模块集成

### 8.1 与 Lead Agent 集成

```python
class LeadAgent:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def understand(self, user_input: str) -> str:
        # 构建包含记忆的上下文
        context = await self.memory.build_context(user_input)

        # 理解意图
        return await self.llm.think(context)
```

### 8.2 与 Evolution 集成

```python
class EvolutionEngine:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def on_skill_created(self, skill: Skill) -> None:
        """技能创建时更新记忆"""
        self.memory.save_knowledge(
            f"skill_{skill.name}",
            f"{skill.description}"
        )

    async def update_preferences(self, preferences: list[Preference]) -> None:
        """更新偏好"""
        for pref in preferences:
            self.memory.save_preference(pref.key, pref.value)
```

---

## 9. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [episodic.md](episodic.md) - Episodic 事件层
- [dream.md](dream.md) - Dream 梦境整合