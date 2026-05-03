# MiniCode 架构设计文档 - Config 配置管理

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 设计目标

**Config 配置管理** - 统一管理配置，支持多层级加载、环境变量覆盖。

### 1.1 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **集中管理** | 配置集中存储 | 易于维护 |
| **层级覆盖** | 支持配置优先级 | 灵活性 |
| **类型安全** | 使用 dataclass | 类型检查 |

### 1.2 为什么这样设计

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| 配置中心化 | 避免散落各处 | 统一管理 |
| 环境变量优先 | 方便运维 | 灵活性 |
| YAML 格式 | 人类可读 | 易维护 |

---

## 2. 模块结构

```
infra/config/
├── __init__.py          # 导出公共类型
├── manager.py           # ConfigManager 配置管理器
└── settings.py         # 配置 dataclass 定义
```

---

## 3. 配置结构

### 3.1 完整配置

```python
@dataclass
class MiniCodeConfig:
    """MiniCode 配置"""
    # 模型配置
    model: ModelConfig = ModelConfig()

    # 会话配置
    session: SessionConfig = SessionConfig()

    # 团队配置
    team: TeamConfig = TeamConfig()

    # 进化配置
    evolution: EvolutionConfig = EvolutionConfig()

    # 权限配置
    permission: PermissionConfig = PermissionConfig()

    # 记忆配置
    memory: MemoryConfig = MemoryConfig()

    # Hook 配置
    hook: HookConfig = HookConfig()
```

### 3.2 子配置

```python
@dataclass
class SessionConfig:
    """会话配置"""
    max_tokens: int = 100_000      # 最大 token 数
    compress_threshold: float = 0.7  # 压缩阈值
    compress_ratio: float = 0.5    # 压缩比例

@dataclass
class TeamConfig:
    """团队配置"""
    max_workers: int = 5          # 最大 worker 数
    timeout: float = 300.0        # 超时时间

@dataclass
class EvolutionConfig:
    """进化配置"""
    enabled: bool = True           # 是否启用
    interval: int = 1800          # 进化间隔（秒）
    min_tasks: int = 10           # 最小任务数触发

@dataclass
class MemoryConfig:
    """记忆配置"""
    max_items: int = 1000         # 最大记忆条数
    ttl: int = 86400 * 30         # TTL（30天）

@dataclass
class HookConfig:
    """Hook 配置"""
    config_path: str = ".minicode/hooks.json"  # 用户 Hook 配置路径
    builtin_enabled: bool = True  # 是否启用内置 Hook
```

---

## 4. ConfigManager 设计

### 4.1 核心接口

```python
class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".minicode" / "config.yaml"
        self._config: Optional[MiniCodeConfig] = None

    def load(self) -> MiniCodeConfig:
        """加载配置"""
        if self._config is None:
            self._config = self._load_from_file()
        return self._config

    def save(self, config: MiniCodeConfig) -> None:
        """保存配置"""
        self._config = config
        self._save_to_file(config)

    def get_model_config(self) -> ModelConfig:
        """获取模型配置"""
        return self.load().model

    def get_session_config(self) -> SessionConfig:
        """获取会话配置"""
        return self.load().session

    def get_team_config(self) -> TeamConfig:
        """获取团队配置"""
        return self.load().team

    def get_evolution_config(self) -> EvolutionConfig:
        """获取进化配置"""
        return self.load().evolution

    def reset(self) -> None:
        """重置配置"""
        self._config = None


# 全局单例
_global_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager
```

### 4.2 配置加载实现

```python
import yaml
import os
from pathlib import Path
from typing import Any

class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self._config: Optional[MiniCodeConfig] = None

    def _load_from_file(self) -> MiniCodeConfig:
        """从文件加载配置"""
        # 1. 加载 YAML 配置
        yaml_config = {}
        if self.config_path and self.config_path.exists():
            yaml_config = yaml.safe_load(self.config_path.read_text()) or {}

        # 2. 从环境变量覆盖
        env_overrides = self._load_env_overrides()

        # 3. 合并配置
        merged = {**yaml_config, **env_overrides}

        # 4. 构建配置对象
        return self._build_config(merged)

    def _load_env_overrides(self) -> dict[str, Any]:
        """加载环境变量覆盖"""
        overrides = {}

        # 模型配置
        if api_key := os.getenv("MINICODE_API_KEY"):
            overrides.setdefault("model", {})["api_key"] = api_key
        if model := os.getenv("MINICODE_MODEL"):
            overrides.setdefault("model", {})["model"] = model
        if base_url := os.getenv("MINICODE_BASE_URL"):
            overrides.setdefault("model", {})["base_url"] = base_url

        # 会话配置
        if max_tokens := os.getenv("MINICODE_MAX_TOKENS"):
            overrides.setdefault("session", {})["max_tokens"] = int(max_tokens)

        return overrides

    def _build_config(self, data: dict) -> MiniCodeConfig:
        """构建配置对象"""
        # 从 dict 构建 dataclass
        # ...
        return MiniCodeConfig()
```

---

## 5. 配置加载优先级

```
1. 环境变量 (优先级最高)
   ├── MINICODE_API_KEY
   ├── MINICODE_MODEL
   ├── MINICODE_BASE_URL
   └── MINICODE_MAX_TOKENS

2. 命令行参数 (次高)
   └── --config, --model 等

3. 配置文件 (中等)
   ├── ~/.minicode/config.yaml (用户级)
   └── ./minicode.yaml (项目级)

4. 默认值 (最低)
   └── 代码中的默认值
```

---

## 6. 配置文件示例

### 6.1 用户级配置 (~/.minicode/config.yaml)

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-7
  api_key: ${MINICODE_API_KEY}  # 从环境变量读取

session:
  max_tokens: 100000
  compress_threshold: 0.7

team:
  max_workers: 5
  timeout: 300

evolution:
  enabled: true
  interval: 1800
  min_tasks: 10

memory:
  max_items: 1000
  ttl: 2592000  # 30 days
```

### 6.2 项目级配置 (./minicode.yaml)

```yaml
model:
  model: claude-opus-4-7  # 覆盖用户配置

team:
  max_workers: 3  # 项目限制
```

---

## 7. 实现要点

1. **延迟加载**：配置按需加载，避免启动开销
2. **缓存**：加载后缓存，避免重复解析
3. **环境变量**：敏感信息从环境变量读取
4. **类型安全**：使用 dataclass 提供类型提示

---

## 8. 参考资料

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)