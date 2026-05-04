# Memory 记忆架构 - Episodic 事件层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Episodic 层职责

Episodic 层负责存储和管理事件记忆：

1. **短期存储** - 记录任务执行过程和结果
2. **LLM 检索** - 语义理解用户意图，匹配相关事件
3. **自动整合** - 配合 Dream 进行去重合并

---

## 2. 操作列表

```python
class EpisodicMemory:
    """事件记忆"""

    def __init__(self, storage_dir: Path, llm):
        self.storage_dir = storage_dir / "episodic"
        self.llm = llm

    # ============ 基础操作 ============

    def save(self, name: str, content: str, memory_type: str) -> None:
        """存入新事件"""

    def get(self, name: str) -> Optional[MemoryEntry]:
        """读取单个事件"""

    def get_all(self) -> list[MemoryEntry]:
        """读取所有事件"""

    def delete(self, name: str) -> None:
        """删除事件"""

    # ============ 检索操作 ============

    async def search(self, query: str) -> str:
        """LLM 语义检索"""

    # ============ 整合操作（Dream 调用）===========

    def consolidate(self) -> dict:
        """整合事件记忆，去重清理"""

    def _get_all_formatted(self) -> str:
        """获取所有记忆，格式化输出（供 LLM 使用）"""
```

---

## 3. 存入（save）

```python
def save(self, name: str, content: str, memory_type: str) -> None:
    """存入新事件"""
    timestamp = int(time.time())
    filename = f"episode_{name}_{timestamp}.md"

    content_md = f"""---
name: {name}
type: {memory_type}
created_at: {timestamp}
access_count: 0
last_accessed: {timestamp}
---

{content}
"""

    (self.storage_dir / filename).write_text(content_md)
```

**触发时机**：
- 任务完成时
- 会话结束时
- 关键决策时

---

## 4. 读取（get / get_all）

```python
def get(self, name: str) -> Optional[MemoryEntry]:
    """读取单个事件"""
    for file in self.storage_dir.glob("*.md"):
        if name in file.name:
            return self._parse(file)
    return None


def get_all(self) -> list[MemoryEntry]:
    """读取所有事件"""
    entries = []
    for file in self.storage_dir.glob("*.md"):
        entry = self._parse(file)
        if entry:
            entries.append(entry)
    return entries
```

---

## 5. 删除（delete）

```python
def delete(self, name: str) -> None:
    """删除事件"""
    for file in self.storage_dir.glob("*.md"):
        if name in file.name:
            file.unlink()
            return
```

**触发时机**：
- Dream 整合时清理过期记忆
- 用户手动删除

---

## 6. LLM 检索（search）

```python
async def search(self, query: str) -> str:
    """LLM 语义检索"""
    memories = self._get_all_formatted()

    prompt = f"""你是记忆检索助手。用户将输入一个问题或请求，你需要从记忆中找出最相关的条目。

用户输入：{query}

--- 现有记忆 ---
{memories}
--- 记忆结束 ---

请找出最相关的记忆（最多 3 条），并说明为什么相关。

格式：
**相关记忆**：
1. [名称] - 相关原因
2. [名称] - 相关原因

如果没有相关记忆，回复："无相关记忆"
"""

    return await self.llm.think(prompt)


def _get_all_formatted(self) -> str:
    """获取所有记忆，格式化输出"""
    memories = []
    for file in self.storage_dir.glob("*.md"):
        entry = self._parse(file)
        if entry:
            memories.append(f"""- 名称: {entry.name}
  类型: {entry.memory_type}
  内容: {entry.content[:200]}...""")

    return "\n".join(memories) if memories else "（暂无记忆）"
```

---

## 7. 整合（consolidate）

Dream 调用此方法清理过期记忆。

```python
def consolidate(self) -> dict:
    """整合事件记忆"""
    by_type: dict[str, list] = {}

    # 按类型分组
    for entry in self.get_all():
        if entry.memory_type not in by_type:
            by_type[entry.memory_type] = []
        by_type[entry.memory_type].append(entry)

    # 每类只保留最新 20 条
    deleted_count = 0
    for mem_type, entries in by_type.items():
        if len(entries) > 20:
            entries.sort(key=lambda e: e.last_accessed, reverse=True)
            for entry in entries[20:]:
                self.delete(entry.name)
                deleted_count += 1

    return {
        "action": "consolidate",
        "remaining": len(self.get_all()),
        "deleted": deleted_count
    }
```

---

## 8. 记忆条目结构

```python
@dataclass
class MemoryEntry:
    """记忆条目"""
    name: str                     # 名称
    content: str                  # 内容
    memory_type: str              # 类型
    created_at: float             # 创建时间
    access_count: int = 0        # 访问次数
    last_accessed: float = 0      # 最后访问时间
```

---

## 9. Markdown 格式

```markdown
---
name: task_pytest_fix_20260503
type: task_completion
created_at: 1714723200
access_count: 5
last_accessed: 1714750000
---

## 任务：修复 pytest import 错误

### 问题
用户运行 pytest 报 import 错误

### 解决
修改 conftest.py，添加 sys.path.insert

### 结果
测试通过
```

---

## 10. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [dream.md](dream.md) - Dream 梦境整合
- [layer.md](layer.md) - 记忆层整合