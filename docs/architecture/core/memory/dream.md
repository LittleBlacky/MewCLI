# Memory 记忆架构 - Dream 梦境整合

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 为什么需要梦境整合

记忆系统在长期使用后会产生以下问题：

- **重复记忆** - 相同信息以不同名称存储多次
- **矛盾记忆** - 不同记忆包含冲突的信息
- **过期记忆** - 某些记忆已不再相关但未被清理
- **索引膨胀** - MEMORY.md 索引超过行数限制

Dream Consolidator 在会话间隙自动运行，分析和整合三层记忆（Preference、Knowledge、Episodic），解决这些问题。

---

## 2. Dream 设计

```python
@dataclass
class DreamConfig:
    """梦境整合配置 - 混合触发模式"""
    # 会话结束时自动触发
    trigger_on_session_end: bool = True

    # 定时触发（分钟）
    schedule_interval_minutes: int = 30

    # 阈值触发
    memory_count_threshold: int = 100

    # 整合深度：light / normal / deep
    consolidation_depth: str = "normal"

    # 冷却时间（秒）
    cooldown_seconds: int = 86400  # 24 小时

    # 最小会话数后才开始整合
    min_session_count: int = 5


class DreamConsolidator:
    """梦境整合器 - 会话间隙自动整合记忆"""

    # 默认配置
    DEFAULT_CONFIG = DreamConfig()

    # 整合阶段
    PHASES = [
        "Orient: scan MEMORY.md index for structure and categories",
        "Gather: read individual memory files for full content",
        "Consolidate: merge related memories, remove stale entries",
        "Prune: enforce 200-line limit on MEMORY.md index",
    ]
```

---

## 3. 触发时机（混合模式）

Dream 使用三种触发机制，确保记忆整合的及时性和资源效率：

| 触发方式 | 说明 | 触发条件 |
|----------|------|----------|
| **会话结束触发** | 用户结束会话时自动执行轻量级整合 | `trigger_on_session_end=True` |
| **定时触发** | 后台定时执行深度整合 | 每 30 分钟 |
| **阈值触发** | 记忆数超过阈值时强制整合 | 记忆数 > 100 |

---

## 4. 触发条件（门控机制）

```python
def should_consolidate(self) -> tuple[bool, str]:
    """判断是否应该执行梦境整合"""
    now = time.time()

    # 条件 1: 梦境整合已启用
    if not self.enabled:
        return False, "consolidation is disabled"

    # 条件 2: 记忆目录存在
    if not self.memory_dir.exists():
        return False, "memory directory does not exist"

    # 条件 3: 存在记忆文件
    memory_files = [f for f in self.memory_dir.glob("*.md") if f.name != "MEMORY.md"]
    if not memory_files:
        return False, "no memory files found"

    # 条件 4: 不是 plan 模式
    if self.mode == "plan":
        return False, "plan mode does not allow consolidation"

    # 条件 5: 冷却时间已过
    time_since_last = now - self.last_consolidation_time
    if time_since_last < self.COOLDOWN_SECONDS:
        return False, f"cooldown active, {int(self.COOLDOWN_SECONDS - time_since_last)}s remaining"

    # 条件 6: 最小会话数
    if self.session_count < self.MIN_SESSION_COUNT:
        return False, f"only {self.session_count} sessions, need {self.MIN_SESSION_COUNT}"

    # 条件 7: 获取锁
    if not self._acquire_lock():
        return False, "lock held by another process"

    return True, "all gates passed"
```

---

## 5. 整合流程

```python
def consolidate(self) -> dict:
    """执行四阶段梦境整合"""
    can_run, reason = self.should_consolidate()
    if not can_run:
        return {"ran": False, "reason": reason}

    # Phase 1-2: 收集所有记忆
    memory_files = [f for f in self.memory_dir.glob("*.md") if f.name != "MEMORY.md"]
    all_memories = {}
    for mf in memory_files:
        parsed = self._parse_frontmatter(mf.read_text())
        if parsed:
            all_memories[mf.name] = parsed

    # Phase 3: LLM 分析
    prompt = """
    You are maintaining a memory store. Analyze these memories and identify:
    1. Duplicates to merge (same concept, different names)
    2. Contradictions to resolve (conflicting advice)
    3. Obsolete entries to delete (no longer relevant)

    Return JSON: {"actions": [{"action": "merge|delete|keep",
    "files": ["file1.md", ...], "new_name": "..."}]}
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    plan = json.loads(response.content)

    # Phase 4: 应用更改
    summary = {"merged": 0, "deleted": 0, "kept": 0}
    for action in plan.get("actions", []):
        act = action.get("action", "keep")
        files = action.get("files", [])

        if act == "merge":
            # 删除原文件，合并保存
            for f in files:
                fp = self.memory_dir / f
                if fp.exists():
                    fp.unlink()
                    summary["deleted"] += 1
            summary["merged"] += 1

        elif act == "delete":
            for f in files:
                fp = self.memory_dir / f
                if fp.exists():
                    fp.unlink()
                    summary["deleted"] += 1

        elif act == "keep":
            summary["kept"] += len(files)

    self.last_consolidation_time = time.time()
    self._release_lock()

    return summary
```

---

## 6. 锁机制（防止并发）

```python
def _acquire_lock(self) -> bool:
    """获取整合锁，防止并发运行"""
    if self.lock_file.exists():
        try:
            pid_str, ts_str = self.lock_file.read_text().strip().split(":", 1)
            pid, lock_time = int(pid_str), float(ts_str)

            # 检查锁是否过期
            if (time.time() - lock_time) > self.LOCK_STALE_SECONDS:
                self.lock_file.unlink()
            else:
                try:
                    os.kill(pid, 0)
                    return False
                except OSError:
                    self.lock_file.unlink()
        except (ValueError, OSError):
            self.lock_file.unlink(missing_ok=True)

    try:
        self.lock_file.write_text(f"{os.getpid()}:{time.time()}")
        return True
    except OSError:
        return False
```

---

## 7. 与记忆层的集成

```python
class MemoryLayer:
    """记忆层"""

    def __init__(self, thread_id: str = "default"):
        self.preference = PreferenceMemory()
        self.knowledge = KnowledgeMemory()
        self.episodic = EpisodicMemory()
        self.dream = DreamConsolidator()

    def on_session_end(self) -> None:
        """会话结束时的钩子"""
        self.dream.session_count += 1
        self.dream.consolidate()

    def on_task_complete(self, task_id: str, result: str) -> None:
        """任务完成时更新事件记忆"""
        self.episodic.save_episode(
            name=f"task_{task_id}_{int(time.time())}",
            content=result,
            memory_type="task_completion",
        )
```

---

## 8. 整合结果示例

```
[Dream] Starting consolidation...
[Dream] Phase 1-2: gathered 15 memories
[Dream] Phase 3: analyzing for duplicates/contradictions...
[Dream] Phase 4: applying changes...
  [Dream] merged ['user_tabs.md', 'pref_indent.md'] → user_code_style.md
  [Dream] deleted ['old_deprecated.md']
[Dream] Done: 1 merged, 1 deleted, 13 kept
```

---

## 9. Lead/Worker 记忆访问模式

**记忆访问权限**：Lead Agent 读写，Worker 只读

| 操作     | Lead Agent | Worker Agent |
| -------- | ---------- | ------------ |
| 创建记忆 | ✓          | ✗            |
| 更新记忆 | ✓          | ✗            |
| 检索记忆 | ✓          | ✓            |
| 删除记忆 | ✓          | ✗            |

---

## 10. 相关文档

- [index.md](index.md) - 记忆架构索引
- [layer.md](layer.md) - 记忆层整合
- [preference.md](preference.md) - Preference 偏好层
- [knowledge.md](knowledge.md) - Knowledge 知识层
- [episodic.md](episodic.md) - Episodic 事件层