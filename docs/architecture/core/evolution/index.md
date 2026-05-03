# Evolution 进化架构 - 文档索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **index** | `core/evolution/index.md` | 总索引 |
| **engine** | `core/evolution/engine.md` | EvolutionEngine、触发机制 |
| **synthesizer** | `core/evolution/synthesizer.md` | SkillSynthesizer 技能生成 |

---

## 模块结构

```
core/evolution/
├── __init__.py              # 导出公共类型
├── engine.py                # EvolutionEngine
└── synthesizer.py           # SkillSynthesizer
```

**说明**：移除了 PatternDetector（模式检测改由 LLM 判断），移除了 memory_updater.py（记忆更新由 Memory Layer 处理）。

**集成说明**：Evolution Engine 调用 `core/skill/` 模块管理技能，而非自行处理。

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **后台异步** | 进化在后台运行，不阻塞主流程 | 保证响应速度 |
| **增量学习** | 从每次任务中学习新知识 | 持续改进 |
| **模式驱动** | 从重复模式中提取通用能力 | 提高效率 |
| **可追溯** | 保存学习历史，支持回溯分析 | 便于调试和优化 |
| **统一存储** | 技能统一保存到 `.minicode/skills/` | 集中管理、可用户编辑 |

---

## 核心设计决策

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| 后台异步进化 | 不影响主流程响应 | 用户体验好 |
| 事件驱动触发 | 任务完成时自动触发 | 自动化 |
| LLM 判断模式 | 语义理解优于频率统计 | 更准确 |
| Skill Synthesizer 技能合成 | 从经验中生成技能 | 可复用 |

---

## 相关文档

- [../../skill/index.md](../../skill/index.md) - Skill 技能系统
- [../../../memory/index.md](../../../memory/index.md) - Memory 记忆系统
- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构