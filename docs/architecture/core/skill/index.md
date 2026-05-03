# Skill 技能系统 - 索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. 概述

**Skill 技能系统** - 独立的业务能力模块，支持用户创建和从经验中自动生成。

### 1.1 为什么 Skill 独立

| 问题 | 解决方案 |
|------|----------|
| Skill 不只是记忆 | Skill 更像"主动能力"，Agent 可以直接调用 |
| 两种来源 | 支持用户创建和从经验中自动生成 |
| 独立生命周期 | 需要独立的注册、匹配、执行机制 |

### 1.2 模块结构

```
core/
└── skill/                   # 技能系统（核心模块）
    ├── __init__.py          # 导出公共类型
    ├── registry.py          # 技能注册表
    └── matcher.py           # 技能匹配器

.minicode/                  # 运行时数据目录
└── skills/                  # Skill 持久化目录
    ├── user/                # 用户创建的技能
    │   └── *.md
    └── auto/                # 经验自动生成的技能
        └── *.md
```

---

## 2. 核心组件

| 组件 | 职责 | 说明 |
|------|------|------|
| **SkillRegistry** | 技能注册表 | 管理技能注册、检索、持久化 |
| **SkillMatcher** | 技能匹配器 | 关键词匹配 + 上下文匹配 |
| **Skill** | 技能定义 | 技能数据结构 |

---

## 3. 技能访问权限

**技能访问权限**：Lead Agent 读写，Worker 只读

| 操作      | Lead Agent | Worker Agent |
| --------- | ---------- | ------------ |
| 创建技能  | ✓          | ✗            |
| 更新技能  | ✓          | ✗            |
| 匹配技能  | ✓          | ✓            |
| 删除技能  | ✓          | ✗            |

---

## 4. 相关文档

- [registry.md](registry.md) - 技能注册表
- [matcher.md](matcher.md) - 技能匹配器
- [index.md](../core/agent/index.md) - Agent 核心架构
- [index.md](../core/evolution/index.md) - Evolution 进化架构