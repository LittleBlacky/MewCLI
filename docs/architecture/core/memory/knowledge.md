# Memory 记忆架构 - Knowledge 知识层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Knowledge 层职责

Knowledge 层负责存储和管理项目知识：

1. **项目信息** - 项目类型、语言、框架等
2. **代码风格** - 编码规范、命名约定等
3. **依赖关系** - 项目依赖、构建方式等

---

## 2. KnowledgeMemory 实现

```python
class KnowledgeMemory:
    """项目知识记忆"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "static"
        self.project_file = self.storage_dir / "project.md"

    def save_project_knowledge(self, key: str, value: str) -> None:
        """保存项目知识"""

    def get_project_knowledge(self) -> str:
        """获取项目知识"""

    def list_knowledge(self) -> list[dict]:
        """列出所有知识"""
```

---

## 3. 存储格式（Markdown）

```markdown
# 项目知识

project_type: python
main_language: python
test_framework: pytest
code_style: pep8
dependencies: requirements.txt
```

---

## 4. 与 Lead Agent 集成

```python
class LeadAgent:
    def build_context(self, user_input: str, memories: dict) -> str:
        """构建包含记忆的上下文"""
        parts = [f"用户输入: {user_input}"]

        # 添加知识
        if memories.get("knowledge"):
            parts.append(f"\n\n# 项目知识\n{memories['knowledge']}")

        return "\n\n".join(parts)
```

---

## 5. 注入时机

| 时机 | 说明 |
|------|------|
| 会话开始 | 自动注入 |
| 按需 | 用户询问相关项目信息时 |

---

## 6. 相关文档

- [index.md](index.md) - 记忆架构索引
- [preference.md](preference.md) - Preference 偏好层
- [episodic.md](episodic.md) - Episodic 事件层
- [layer.md](layer.md) - 记忆层整合