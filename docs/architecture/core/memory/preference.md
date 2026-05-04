# Memory 记忆架构 - Preference 偏好层

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Preference 层职责

Preference 层负责存储和管理用户偏好：

1. **长期存储** - 用户偏好持久化存储
2. **直接读取** - 会话开始时直接注入
3. **按需更新** - 支持运行时更新偏好

---

## 2. 操作列表

```python
class PreferenceMemory:
    """用户偏好记忆"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "static"
        self.preferences_file = self.storage_dir / "preferences.md"

    # ============ 基础操作 ============

    def save(self, key: str, value: str) -> None:
        """存入/更新偏好"""

    def get(self, key: str) -> Optional[str]:
        """读取单个偏好"""

    def get_all(self) -> str:
        """读取全部偏好（格式化）"""

    def update(self, key: str, value: str) -> None:
        """更新偏好（等同于 save）"""

    def delete(self, key: str) -> None:
        """删除偏好"""

    def list_all(self) -> list[dict]:
        """列出所有偏好"""
```

---

## 3. 存入（save）

```python
def save(self, key: str, value: str) -> None:
    """存入/更新偏好"""
    preferences = self._load_preferences()
    preferences[key] = value
    self._save_preferences(preferences)


def _load_preferences(self) -> dict[str, str]:
    """加载偏好文件"""
    if not self.preferences_file.exists():
        return {}
    content = self.preferences_file.read_text()
    # 解析 markdown 格式：key: value
    preferences = {}
    for line in content.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            preferences[key.strip()] = value.strip()
    return preferences


def _save_preferences(self, preferences: dict[str, str]) -> None:
    """保存偏好文件"""
    lines = ["# 用户偏好"]
    for key, value in preferences.items():
        lines.append(f"{key}: {value}")
    self.preferences_file.write_text("\n".join(lines))
```

**触发时机**：
- 用户设置偏好（如 `set tab_size=4`）
- Evolution 进化出新的偏好

---

## 4. 读取（get / get_all）

```python
def get(self, key: str) -> Optional[str]:
    """读取单个偏好"""
    preferences = self._load_preferences()
    return preferences.get(key)


def get_all(self) -> str:
    """读取全部偏好（格式化，供上下文使用）"""
    if not self.preferences_file.exists():
        return ""
    return self.preferences_file.read_text()
```

---

## 5. 更新（update）

```python
def update(self, key: str, value: str) -> None:
    """更新偏好"""
    # 等同于 save
    self.save(key, value)
```

---

## 6. 删除（delete）

```python
def delete(self, key: str) -> None:
    """删除偏好"""
    preferences = self._load_preferences()
    if key in preferences:
        del preferences[key]
        self._save_preferences(preferences)
```

---

## 7. 列出（list_all）

```python
def list_all(self) -> list[dict]:
    """列出所有偏好"""
    preferences = self._load_preferences()
    return [{"key": k, "value": v} for k, v in preferences.items()]
```

---

## 8. 存储格式（Markdown）

```markdown
# 用户偏好

tab_size: 4
indent_style: space
auto_save: true
permission_mode: prompt
```

---

## 9. 与其他模块集成

```python
class LeadAgent:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory = memory_layer

    async def build_system_prompt(self) -> str:
        """构建 System Prompt"""
        preferences = self.memory.preference.get_all()

        return f"""你是 AI 助手。

# 用户偏好
{preferences}

---
现在开始对话...
"""
```

---

## 10. 相关文档

- [index.md](index.md) - 记忆架构索引
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [episodic.md](episodic.md) - Episodic 事件层
- [dream.md](dream.md) - Dream 梦境整合
- [layer.md](layer.md) - 记忆层整合