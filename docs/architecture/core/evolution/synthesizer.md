# Evolution 进化架构 - SkillSynthesizer

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. SkillSynthesizer 职责

SkillSynthesizer 负责从经验中生成技能：

1. **模板匹配** - 根据任务类型匹配技能模板
2. **技能生成** - 生成新的技能定义
3. **技能存储** - 保存技能到记忆系统

---

## 2. 技能模板

```python
@dataclass
class SkillTemplate:
    """技能模板"""
    name: str                            # 技能名称
    description: str                     # 技能描述
    trigger_keywords: list[str]          # 触发关键词
    prompt_template: str                # LLM 提示模板
    expected_tools: list[str]           # 期望的工具
    success_pattern: str = ""            # 成功模式
    failure_pattern: str = ""            # 失败模式
```

---

## 3. 生成流程

```python
class SkillSynthesizer:
    def __init__(self, memory_layer: MemoryLayer):
        self.memory_layer = memory_layer
        self._templates = self._load_default_templates()

    async def synthesize(self, pattern: DetectedPattern) -> Optional[Skill]:
        """从模式合成技能"""
        # 1. 匹配模板
        template = self._find_template(pattern.pattern_type)
        if not template:
            return None

        # 2. 收集相关事件
        events = self._collect_related_events(pattern)

        # 3. 生成技能
        skill = await self._generate_skill(template, events)

        # 4. 保存技能（通过 SkillRegistry 统一保存到 .minicode/skills/）
        if skill:
            await self.skill_registry.save(skill)

        return skill

    def _find_template(self, pattern_type: str) -> Optional[SkillTemplate]:
        """查找匹配的模板"""
        return self._templates.get(pattern_type)

    async def _generate_skill(
        self,
        template: SkillTemplate,
        events: list[EvolutionEvent],
    ) -> Optional[Skill]:
        """使用 LLM 生成技能"""
        # 构建提示
        prompt = f"""
        基于以下 {len(events)} 个事件，生成一个技能：

        模板：{template.prompt_template}

        事件：
        {self._format_events(events)}

        请生成：
        1. 技能名称
        2. 技能描述
        3. 触发条件
        4. 执行步骤
        """

        # 调用 LLM 生成
        result = await llm.think(prompt)

        # 解析结果
        return self._parse_skill(result, template)
```

---

## 4. 默认模板

```python
DEFAULT_TEMPLATES = {
    "bug": SkillTemplate(
        name="Bug 修复流程",
        description="标准的 bug 修复流程",
        trigger_keywords=["bug", "fix", "error", "issue"],
        prompt_template="分析 bug → 复现 → 修复 → 测试",
        expected_tools=["read_file", "bash", "search"],
    ),
    "refactor": SkillTemplate(
        name="代码重构流程",
        description="标准的代码重构流程",
        trigger_keywords=["refactor", "improve", "clean"],
        prompt_template="分析 → 规划 → 执行 → 验证",
        expected_tools=["read_file", "write_file"],
    ),
    "test": SkillTemplate(
        name="测试流程",
        description="标准的测试执行流程",
        trigger_keywords=["test", "testing"],
        prompt_template="编写测试 → 执行 → 验证",
        expected_tools=["bash", "write_file"],
    ),
}
```

---

## 5. 事件收集

```python
class SkillSynthesizer:
    def _collect_related_events(self, pattern: DetectedPattern) -> list[EvolutionEvent]:
        """收集相关的历史事件"""
        related = []
        for event in self._event_history:
            if self._matches_pattern(event, pattern):
                related.append(event)
                if len(related) >= 5:  # 最多收集 5 个事件
                    break
        return related

    def _matches_pattern(self, event: EvolutionEvent, pattern: DetectedPattern) -> bool:
        """判断事件是否匹配模式"""
        # 简化版：只检查类型匹配
        return event.event_type == pattern.trigger_type
```

---

## 6. 相关文档

- [engine.md](engine.md) - EvolutionEngine 实现
- [../../skill/index.md](../../skill/index.md) - Skill 技能系统
- [../../../memory/index.md](../../../memory/index.md) - Memory 记忆系统