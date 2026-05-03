# Session 会话架构 - Checkpoint 断点持久化

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Checkpoint 概述

Checkpoint 用于会话断点持久化，支持断点续连和状态恢复。

---

## 2. 会话断点配置

```python
@dataclass
class CheckpointConfig:
    """断点配置"""
    enabled: bool = True                    # 是否启用断点
    save_interval: float = 30.0             # 保存间隔（秒）
    max_checkpoints: int = 10              # 最大断点数
    storage_dir: Path = None                # 存储目录
```

---

## 3. Checkpoint 管理

### 3.1 保存断点

```python
class CheckpointManager:
    """断点管理器"""

    def __init__(self, config: CheckpointConfig):
        self.config = config
        self.storage_dir = config.storage_dir or Path.home() / ".minicode" / "checkpoints"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def save_checkpoint(self, session: SessionContext) -> str:
        """保存断点"""
        checkpoint_id = f"checkpoint_{session.id}_{int(time.time())}"
        filepath = self.storage_dir / f"{checkpoint_id}.json"

        data = session.to_dict()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        return checkpoint_id
```

### 3.2 加载断点

```python
    async def load_checkpoint(self, checkpoint_id: str) -> Optional[SessionContext]:
        """加载断点"""
        filepath = self.storage_dir / f"{checkpoint_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            return SessionContext.from_dict(data)
        return None
```

### 3.3 清理旧断点

```python
    async def cleanup_old_checkpoints(self, session_id: str) -> None:
        """清理旧断点"""
        checkpoints = sorted(
            self.storage_dir.glob(f"checkpoint_{session_id}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for checkpoint in checkpoints[self.config.max_checkpoints:]:
            checkpoint.unlink()
```

---

## 4. 与 SessionManager 集成

```python
class SessionManager:
    def __init__(self, checkpoint_config: Optional[CheckpointConfig] = None):
        self.checkpoint_manager = CheckpointManager(checkpoint_config) if checkpoint_config else None

    async def on_auto_save(self, session: SessionContext) -> None:
        """自动保存触发"""
        if self.checkpoint_manager:
            await self.checkpoint_manager.save_checkpoint(session)
```

---

## 5. 相关文档

- [context.md](context.md) - SessionContext 实现
- [manager.md](manager.md) - SessionManager 实现
- [../../infra/checkpoint.md](../../infra/checkpoint.md) - 通用 Checkpoint 系统