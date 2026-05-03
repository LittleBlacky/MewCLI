# Memory 记忆架构 - Preference 偏好层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Preference 层职责

Preference 层负责存储和管理用户偏好：

1. **长期存储** - 用户偏好持久化存储
2. **自动注入** - 会话开始时自动注入
3. **按需更新** - 支持运行时更新偏好

---

## 2. PreferenceMemory 实现

```python
class PreferenceMemory:
    """用户偏好记忆"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "static"
        self.preferences_file = self.storage_dir / "preferences.md"

    def save_preference(self, key: str, value: str) -> None:
        """保存偏好"""

    def get_preferences(self) -> str:
        """获取偏好，返回格式化文本"""

    def list_preferences(self) -> list[dict]:
        """列出所有偏好"""
```

---

## 3. 存储格式（Markdown）

```markdown
# 用户偏好

tab_size: 4
indent_style: space
auto_save: true
permission_mode: prompt
```

---

## 4. 与 Lead Agent 集成

```python
class LeadAgent:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    def build_context(self, user_input: str, memories: dict) -> str:
        """构建包含记忆的上下文"""
        parts = [f"用户输入: {user_input}"]

        # 添加偏好
        if memories.get("preference"):
            parts.append(f"\n\n# 用户偏好\n{memories['preference']}")

        return "\n\n".join(parts)
```

---

## 5. 注入时机

Preference 层在会话开始时自动注入到 System Prompt。

---

## 6. 相关文档

- [index.md](index.md) - 记忆架构索引
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [episodic.md](episodic.md) - Episodic 事件层
- [dream.md](dream.md) - Dream 梦境整合
- [layer.md](layer.md) - 记忆层整合