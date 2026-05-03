# Memory 记忆架构 - Episodic 事件层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Episodic 层职责

Episodic 层负责存储和管理事件记忆：

1. **短期存储** - 记录任务执行过程和结果
2. **按需检索** - 根据查询条件检索相关事件
3. **自动整合** - 配合 Dream 进行去重合并

---

## 2. EpisodicMemory 实现

```python
class EpisodicMemory:
    """事件记忆"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "episodic"

    def save_episode(self, name: str, content: str, memory_type: str) -> None:
        """保存事件"""

    def search(self, query: str, limit: int = 3) -> list[MemoryEntry]:
        """检索相关事件"""

    def consolidate(self) -> None:
        """整合事件记忆"""
```

---

## 3. 记忆条目结构

```python
@dataclass
class MemoryEntry:
    """记忆条目"""
    name: str                     # 名称
    description: str              # 描述
    content: str                  # 内容
    memory_type: str              # 类型
    created_at: float              # 创建时间
    access_count: int = 0         # 访问次数
    last_accessed: float = 0      # 最后访问时间
```

---

## 4. Markdown 格式

```markdown
---
name: {name}
description: {description}
type: {memory_type}
created_at: {created_at}
access_count: {access_count}
---

{content}
```

---

## 5. 检索策略

```python
class MemoryLayer:
    def should_retrieve_episodic(self, query: str) -> bool:
        """判断是否需要检索事件记忆"""
        # 条件 1: 查询长度 > 15
        if len(query) < 15:
            return False

        # 条件 2: 不是命令
        if query.startswith("/"):
            return False

        # 条件 3: 引用过去
        past_keywords = ["之前", "上次", "记得", "之前做", "以前"]
        if any(kw in query for kw in past_keywords):
            return True

        # 条件 4: 复杂任务
        if len(query) > 100:
            return True

        return False
```

---

## 6. 搜索算法

```python
class MemoryIndex:
    def search(self, query: str, memory_type: Optional[str] = None, limit: int = 3) -> list[MemoryEntry]:
        """搜索相关记忆"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for name, entry in self._index.items():
            if memory_type and entry.memory_type != memory_type:
                continue

            score = 0
            # 名称匹配
            if query_lower in entry.name.lower():
                score += 10
            # 描述匹配
            if query_lower in entry.description.lower():
                score += 5
            # 内容匹配
            for word in query_words:
                if word in entry.content.lower():
                    score += 1
            # 访问次数加成
            score += min(entry.access_count * 0.1, 2)

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]

        # 更新访问统计
        for entry in results:
            entry.access_count += 1
            entry.last_accessed = time.time()
            self.save_entry(entry)

        return results
```

---

## 7. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [dream.md](dream.md) - Dream 梦境整合
- [layer.md](layer.md) - 记忆层整合