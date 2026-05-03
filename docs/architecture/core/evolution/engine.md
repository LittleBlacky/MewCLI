# Evolution 进化架构 - EvolutionEngine

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Evolution Engine 职责

EvolutionEngine 是进化的核心，负责：

1. **任务评估** - 评估任务完成质量（分数 >= 7.0 触发）
2. **LLM 判断** - 使用 LLM 判断是否形成模式
3. **技能生成** - 从经验中生成可复用的技能
4. **记忆更新** - 更新偏好和知识
5. **指标追踪** - 追踪进化效果

**简化说明**：移除了 PatternDetector（频率统计），改用 LLM 直接判断模式。

---

## 2. 核心方法

```python
class EvolutionEngine:
    """进化引擎"""

    def __init__(
        self,
        skill_registry: SkillRegistry,            # Skill 注册表
        storage_dir: Optional[Path] = None,       # 仅为模式历史
        pattern_threshold: int = 3,    # 模式检测阈值
        skill_threshold: int = 5,      # 技能生成阈值
    ):
        self.skill_registry = skill_registry        # 统一保存到 .minicode/skills/
        self.storage_dir = storage_dir or Path.home() / ".minicode" / "evolution"
        self.pattern_threshold = pattern_threshold
        self.skill_threshold = skill_threshold

        self._event_history: list[EvolutionEvent] = []
        self._patterns: dict[str, DetectedPattern] = {}

    async def record_event(self, event: EvolutionEvent) -> Optional[EvolutionTrigger]:
        """记录事件"""

    async def analyze(self, trigger: EvolutionTrigger) -> EvolutionResult:
        """分析事件"""

    async def create_skill(self, pattern_type: str, template: SkillTemplate) -> str:
        """创建技能"""
```

---

## 3. 触发机制

### 3.1 触发类型

```python
class EvolutionTrigger(Enum):
    """进化触发类型"""
    TASK_COMPLETE = "task_complete"      # 任务完成
    TASK_FAILED = "task_failed"         # 任务失败
    HIGH_QUALITY_TASK = "high_quality_task"  # 高质量任务（LLM 评估分数 >= 7.0）
    MANUAL = "manual"                    # 手动触发
```

### 3.2 触发路径（简化版）

| 触发类型 | 来源 | 条件 | 说明 |
|----------|------|------|------|
| **即时评估** | MVP | 分数 >= 7.0 且步数 >= 3 | 好任务立即提取技能 |
| **LLM 判断** | 架构设计 | 任务完成时 | LLM 判断是否创建/更新技能 |

---

## 4. 即时评估触发（来自 MVP）

```python
class EvolutionEngine:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        storage_dir: Optional[Path] = None,
        skill_threshold: float = 7.0,    # MVP 中的评估分数阈值
        min_steps: int = 3,             # MVP 中的最小步数
        pattern_threshold: int = 3,     # 模式检测阈值
    ):
        self.skill_threshold = skill_threshold
        self.min_steps = min_steps
        self.pattern_threshold = pattern_threshold

    async def on_task_complete(self, result: TaskResult) -> None:
        """任务完成时调用 - 实时触发（不等待模式积累）"""
        event = EvolutionEvent(
            event_type=EvolutionTrigger.TASK_COMPLETE,
            task_id=result.task_id,
            description=result.description,
            success=result.success,
            duration=result.duration,
            score=result.score,           # 评估分数
            step_count=result.step_count,  # 执行步数
        )

        # 1. 即时触发：高评分任务立即创建技能
        if self._should_create_skill_immediately(event):
            await self._create_skill_from_task(event)

        # 2. 事件记录：用于后续模式检测
        trigger = await self.record_event(event)

        # 3. 后台模式检测（异步，不阻塞）
        if trigger == EvolutionTrigger.PATTERN_DETECTED:
            asyncio.create_task(self._process_pattern_trigger(trigger))

    def _should_create_skill_immediately(self, event: EvolutionEvent) -> bool:
        """检查是否应该立即创建技能（MVP 逻辑）"""
        return (
            event.score >= self.skill_threshold        # 评分 >= 7.0
            and event.step_count >= self.min_steps    # 步数 >= 3
            and event.success                          # 任务成功
            and not self._has_existing_skill(event.task_type)  # 无匹配技能
        )
```

---

## 5. LLM 判断（替代频率统计）

```python
class EvolutionEngine:
    def __init__(self, ...):
        self._cooldowns: dict[str, float] = {}  # 防止重复触发（按技能名冷却）

    async def on_task_complete(self, result: TaskResult) -> None:
        """任务完成时调用"""
        event = EvolutionEvent(
            event_type=EvolutionTrigger.TASK_COMPLETE,
            task_id=result.task_id,
            description=result.description,
            success=result.success,
            duration=result.duration,
            score=result.score,
            step_count=result.step_count,
        )

        # 1. 即时触发：高评分任务立即创建技能
        if result.score >= self.skill_threshold and result.step_count >= self.min_steps:
            await self._create_skill_from_task(event)
            return

        # 2. 后台 LLM 判断：是否有重复模式值得聚合（异步，不阻塞）
        asyncio.create_task(self._llm_check_pattern(event))

    async def _llm_check_pattern(self, event: EvolutionEvent) -> None:
        """让 LLM 判断是否应该创建/更新技能"""
        # 获取历史相似任务
        similar = self._get_recent_tasks(limit=10)
        similar_text = "\n".join([
            f"- [{t.timestamp}] {t.description} (score={t.score})"
            for t in similar
        ])

        prompt = f"""
你是一个技能进化引擎。分析当前任务和历史任务，判断是否应该创建或更新技能。

当前任务：
- 描述：{event.description}
- 成功：{event.success}
- 分数：{event.score}

最近历史任务：
{similar_text if similar_text else "(无)"}

判断（JSON 格式）：
{{
    "action": "create|update|skip",
    "skill_name": "技能名称（仅当 action 是 create/update 时）",
    "reason": "判断理由"
}}

规则：
- create：当前任务代表一个新模式，值得创建技能
- update：当前任务与已有技能相似，应该更新
- skip：当前任务没有形成模式，不需要操作
"""
        response = await llm.think(prompt)

        try:
            decision = json.loads(response)
            action = decision.get("action", "skip")

            if action in ("create", "update"):
                skill_name = decision.get("skill_name", f"skill_{int(time.time())}")

                # 检查冷却
                if not self._in_cooldown(skill_name):
                    await self._create_or_update_skill(event, skill_name, action)
                    self._cooldowns[skill_name] = time.time() + 3600  # 1小时冷却

        except json.JSONDecodeError:
            pass  # LLM 返回格式错误，忽略

    def _in_cooldown(self, skill_name: str) -> bool:
        """检查是否在冷却期"""
        cooldown_end = self._cooldowns.get(skill_name, 0)
        return time.time() < cooldown_end
```

**优点**：
- LLM 理解语义，不依赖关键词匹配
- 考虑历史上下文，判断更准确
- 避免画蛇添足的频率统计

---

## 6. 完整触发流程

```
                    任务执行完成
                         │
                         ▼
              ┌─────────────────────────┐
              │   评估任务             │
              │   score >= 7.0?       │
              │   step_count >= 3?     │
              └───────────┬───────────┘
                         │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
        是（好任务）                    否（普通任务）
          │                               │
          ▼                               ▼
    ┌──────────────┐            ┌─────────────────────┐
    │ 创建技能     │            │  后台 LLM 判断     │
    │ (立即执行)  │            │  (异步，不阻塞)   │
    └──────────────┘            └──────────┬──────────┘
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                              ▼                         ▼
                          create/update                skip
                              │                         │
                              ▼                         │
                    ┌──────────────┐           │
                    │ 检查冷却     │           │
                    └──────┬───────┘           │
                           │                   │
                    ┌──────┴───────┐           │
                    │             │           │
                    ▼             ▼           │
                 冷却中        可执行         │
                    │             │           │
                    │             ▼           │
                    │     ┌──────────────┐    │
                    │     │ 创建/更新   │    │
                    │     │ 技能        │    │
                    │     └──────┬───────┘    │
                    │            │             │
                    ▼            ▼             ▼
              (跳过)      ┌──────────────┐   (结束)
                          │ 更新记忆     │
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ 更新指标     │
                          └──────────────┘
```

---

## 7. 与 Dream Consolidation 的协作

> Dream Consolidation 是 **Memory 层**的组件，不属于 Evolution 层。详见 [Memory 架构文档](../../../memory/index.md)。

```
┌─────────────────────────────────────────────────────────────┐
│                      Memory Layer                           │
│                   (Dream Consolidation)                     │
│  跨会话整合：合并重复记忆、删除过时记忆、解决矛盾记忆        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 更新记忆
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Evolution Layer                         │
│  模式检测 → 技能生成 → 通知 Memory 更新                      │
└─────────────────────────────────────────────────────────────┘
```

**协作流程**：
1. Evolution Engine 检测到模式，创建技能
2. Evolution Engine 更新 Preference/Knowledge（通过 Memory Layer API）
3. Dream Consolidation 在会话间隙整合这些记忆
4. 整合后的记忆被 Evolution Engine 在下一轮使用

---

## 8. Evolution Event 定义

```python
@dataclass
class EvolutionEvent:
    """进化事件"""
    event_type: EvolutionTrigger       # 事件类型
    task_id: str                       # 关联任务 ID
    description: str                    # 任务描述
    success: bool                       # 是否成功
    duration: float = 0.0              # 执行时长
    error: str = ""                     # 错误信息
    timestamp: float                    # 时间戳
    metadata: dict                      # 额外元数据
```

---

## 9. Evolution Result 定义

```python
@dataclass
class EvolutionResult:
    """进化结果"""
    trigger: EvolutionTrigger                    # 触发类型
    timestamp: float                            # 时间戳
    skills_created: list[str]                   # 创建的技能
    memories_updated: list[str]                 # 更新的记忆
    suggestions: list[str]                      # 建议
    stats: dict                                  # 统计信息
```

---

## 10. 进化指标

```python
@dataclass
class EvolutionMetrics:
    """进化指标"""
    # 技能库指标
    skills_created: int = 0
    skills_auto_created: int = 0
    skills_user_created: int = 0
    skills_template_created: int = 0
    skills_used: int = 0
    skills_hit: int = 0

    # LLM 判断指标（替代模式检测）
    llm_checks: int = 0                    # LLM 判断次数
    llm_create_decisions: int = 0         # LLM 判断创建次数
    llm_skip_decisions: int = 0            # LLM 判断跳过次数

    # 学习效果指标
    learning_sessions: int = 0
    learning_accuracy: float = 0.0
    improvement_score: float = 0.0
```

---

## 11. 相关文档

- [synthesizer.md](synthesizer.md) - SkillSynthesizer 实现
- [../../../memory/index.md](../../../memory/index.md) - Memory 记忆系统
- [../../skill/index.md](../../skill/index.md) - Skill 技能系统