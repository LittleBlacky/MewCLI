# Skill 技能系统 - 技能注册表

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. Skill 定义

### 1.1 数据结构

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class SkillSource(Enum):
    """技能来源"""
    AUTO = "auto"           # 从经验中自动生成
    USER = "user"           # 用户手动创建

@dataclass
class Skill:
    """技能定义"""
    name: str                         # 技能名称
    description: str                  # 技能描述
    content: str                      # 技能内容（prompt 或代码）
    source: SkillSource               # 来源（auto/user）
    trigger_keywords: list[str]       # 触发关键词
    trigger_context: list[str]        # 触发上下文条件
    created_at: float                 # 创建时间
    updated_at: float                 # 更新时间
    usage_count: int = 0             # 使用次数
    tags: list[str] = field(default_factory=list)  # 标签
```

### 1.2 Skill 存储格式

```markdown
---
name: bug_fix_flow
description: 标准的 bug 修复流程
source: auto
trigger_keywords: [bug, fix, error, issue]
trigger_context: [code_file_exists]
created_at: 1715000000
updated_at: 1715000000
usage_count: 15
tags: [bug, fix, workflow]
---

# Bug 修复流程

## 描述
标准的 bug 修复流程：分析 → 复现 → 修复 → 测试

## 内容
```
# 步骤 1: 分析 bug
read_file("buggy_file.py")

# 步骤 2: 复现
bash("python test_bug.py")

# 步骤 3: 修复
write_file("buggy_file.py", "fixed_code")

# 步骤 4: 测试
bash("pytest")
```
```

---

## 2. SkillRegistry 实现

```python
from pathlib import Path
from itertools import chain
from typing import Optional

class SkillRegistry:
    """技能注册表"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._index: dict[str, Skill] = {}
        self._load_index()

    def register(self, skill: Skill) -> None:
        """注册技能"""
        self._index[skill.name] = skill
        self._save_skill(skill)

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._index.get(name)

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

    def _load_index(self) -> None:
        """加载索引"""
        user_dir = self.skills_dir / "user"
        auto_dir = self.skills_dir / "auto"

        for skill_file in chain(user_dir.glob("*.md"), auto_dir.glob("*.md")):
            skill = self._load_skill(skill_file)
            if skill:
                self._index[skill.name] = skill

    def _load_skill(self, path: Path) -> Optional[Skill]:
        """从文件加载技能"""
        content = path.read_text()
        # 解析 frontmatter 和内容
        ...

    def _save_skill(self, skill: Skill) -> None:
        """保存技能到文件"""
        dir_path = self.skills_dir / skill.source.value
        dir_path.mkdir(parents=True, exist_ok=True)

        content = f"""---
name: {skill.name}
description: {skill.description}
source: {skill.source.value}
trigger_keywords: {skill.trigger_keywords}
created_at: {skill.created_at}
updated_at: {skill.updated_at}
usage_count: {skill.usage_count}
---

{skill.content}
"""
        (dir_path / f"{skill.name}.md").write_text(content)
```

---

## 3. 目录结构

```
.minicode/
└── skills/
    ├── user/                # 用户创建的技能
    │   └── my_skill.md
    └── auto/                # 经验自动生成的技能
        └── bug_fix_flow.md
```

---

## 4. 相关文档

- [index.md](index.md) - Skill 技能系统索引
- [matcher.md](matcher.md) - 技能匹配器