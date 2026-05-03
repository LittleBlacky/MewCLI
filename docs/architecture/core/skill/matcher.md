# Skill 技能系统 - 技能匹配器

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 匹配策略

技能匹配采用多维度评分机制：

| 维度 | 权重 | 说明 |
|------|------|------|
| **关键词匹配** | 10 分/个 | 触发关键词命中越多分数越高 |
| **上下文匹配** | 5 分/个 | 当前上下文条件匹配 |
| **使用次数** | 0.1 分/次 | 使用次数越多分数越高（上限 2 分） |

---

## 2. 匹配算法

```python
def match(self, query: str, context: dict = None) -> list[Skill]:
    """匹配技能"""
    matched = []
    for skill in self._index.values():
        score = self._calculate_match_score(skill, query, context)
        if score > 0:
            matched.append((score, skill))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [skill for _, skill in matched[:3]]

def _calculate_match_score(self, skill: Skill, query: str, context: dict) -> float:
    """计算匹配分数"""
    score = 0
    query_lower = query.lower()

    # 关键词匹配
    for keyword in skill.trigger_keywords:
        if keyword.lower() in query_lower:
            score += 10

    # 上下文匹配
    for ctx in skill.trigger_context:
        if context and context.get(ctx):
            score += 5

    # 使用次数加成
    score += min(skill.usage_count * 0.1, 2)

    return score
```

---

## 3. 与 Lead Agent 集成

```python
class LeadAgent:
    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry

    async def understand_and_match(self, user_input: str) -> str:
        """理解输入并匹配技能"""
        # 1. 匹配技能
        matched_skills = self.skill_registry.match(user_input, self.context)

        # 2. 构建上下文
        context = user_input
        for skill in matched_skills:
            context += f"\n\n## 相关技能: {skill.name}\n{skill.content}"
            skill.usage_count += 1

        # 3. 理解意图
        return await self.llm.think(context)
```

---

## 4. 边界条件处理

1. **Skill 不存在**：返回空列表，不报错
2. **重复注册**：覆盖已有 Skill，更新时间戳
3. **关键词冲突**：多个 Skill 触发时，按分数排序返回前 3 个

---

## 5. 相关文档

- [index.md](index.md) - Skill 技能系统索引
- [registry.md](registry.md) - 技能注册表