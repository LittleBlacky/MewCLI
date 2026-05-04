# Memory 记忆架构 - Knowledge 知识层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Knowledge 层职责

Knowledge 层负责存储和管理项目知识：

1. **项目信息** - 项目类型、语言、框架等
2. **代码风格** - 编码规范、命名约定等
3. **直接读取** - 会话开始时直接注入

---

## 2. 操作列表

```python
class KnowledgeMemory:
    """项目知识记忆"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "static"
        self.project_file = self.storage_dir / "project.md"

    # ============ 基础操作 ============

    def save(self, key: str, value: str) -> None:
        """存入/更新知识"""

    def get(self, key: str) -> Optional[str]:
        """读取单个知识"""

    def get_all(self) -> str:
        """读取全部知识（格式化）"""

    def get_project_knowledge(self) -> str:
        """读取项目知识（等同于 get_all）"""

    def update(self, key: str, value: str) -> None:
        """更新知识（等同于 save）"""

    def delete(self, key: str) -> None:
        """删除知识"""

    def list_all(self) -> list[dict]:
        """列出所有知识"""
```

---

## 3. 存入（save）

```python
def save(self, key: str, value: str) -> None:
    """存入/更新知识"""
    knowledge = self._load_knowledge()
    knowledge[key] = value
    self._save_knowledge(knowledge)


def _load_knowledge(self) -> dict[str, str]:
    """加载知识文件"""
    if not self.project_file.exists():
        return {}
    content = self.project_file.read_text()
    # 解析 markdown 格式
    knowledge = {}
    for line in content.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            knowledge[key.strip()] = value.strip()
    return knowledge


def _save_knowledge(self, knowledge: dict[str, str]) -> None:
    """保存知识文件"""
    lines = ["# 项目知识"]
    for key, value in knowledge.items():
        lines.append(f"{key}: {value}")
    self.project_file.write_text("\n".join(lines))
```

**触发时机**：
- 项目初始化时（自动扫描）
- 用户手动添加
- Evolution 更新时

---

## 4. 读取（get / get_all）

```python
def get(self, key: str) -> Optional[str]:
    """读取单个知识"""
    knowledge = self._load_knowledge()
    return knowledge.get(key)


def get_all(self) -> str:
    """读取全部知识（格式化，供上下文使用）"""
    if not self.project_file.exists():
        return ""
    return self.project_file.read_text()


def get_project_knowledge(self) -> str:
    """读取项目知识"""
    return self.get_all()
```

---

## 5. 更新（update）

```python
def update(self, key: str, value: str) -> None:
    """更新知识"""
    # 等同于 save
    self.save(key, value)
```

---

## 6. 删除（delete）

```python
def delete(self, key: str) -> None:
    """删除知识"""
    knowledge = self._load_knowledge()
    if key in knowledge:
        del knowledge[key]
        self._save_knowledge(knowledge)
```

---

## 7. 列出（list_all）

```python
def list_all(self) -> list[dict]:
    """列出所有知识"""
    knowledge = self._load_knowledge()
    return [{"key": k, "value": v} for k, v in knowledge.items()]
```

---

## 8. 存储格式（Markdown）

```markdown
# 项目知识

project_type: python
main_language: python
test_framework: pytest
code_style: pep8
dependencies: requirements.txt
build_command: pytest
```

---

## 9. 与其他模块集成

```python
class LeadAgent:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def build_system_prompt(self) -> str:
        """构建 System Prompt"""
        knowledge = self.memory.knowledge.get_all()

        return f"""你是 AI 助手。

# 项目知识
{knowledge}

---
现在开始对话...
"""
```

---

## 10. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [episodic.md](episodic.md) - Episodic 事件层
- [dream.md](dream.md) - Dream 梦境整合
- [layer.md](layer.md) - 记忆层整合