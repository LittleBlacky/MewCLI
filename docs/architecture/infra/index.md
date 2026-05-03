# MiniCode 架构设计文档 - Infrastructure 基础设施架构

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 概述

**Infrastructure 基础设施** - 为整个系统提供底层支持，包括状态图、模型抽象、配置管理、断点持久化、通用 Hook。

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **Graph 状态图** | `infra/graph.md` | GraphBuilder、GraphState、LangGraph 集成 |
| **Model 模型层** | `infra/model.md` | ModelClient、PromptCache、多厂商支持 |
| **Config 配置管理** | `infra/config.md` | ConfigManager、配置加载优先级 |
| **Checkpoint 持久化** | `infra/checkpoint.md` | CheckpointStore、CheckpointManager、自动保存策略 |
| **Hook 生命周期** | `infra/hook.md` | HookRegistry、@auto_hook、双轨制设计 |

---

## 模块结构

```
infra/
├── graph/                   # LangGraph 封装
│   ├── __init__.py
│   ├── builder.py           # GraphBuilder
│   └── state.py             # Graph State 定义
├── model/                   # 模型抽象
│   ├── __init__.py
│   ├── client.py            # ModelClient
│   └── config.py            # ModelConfig
├── config/                  # 配置管理
│   ├── __init__.py
│   ├── manager.py           # ConfigManager
│   └── settings.py          # 配置定义
├── checkpoint/              # 断点持久化
│   ├── __init__.py
│   ├── store.py             # CheckpointStore
│   └── manager.py           # CheckpointManager
├── hook/                    # 通用生命周期钩子
│   ├── __init__.py
│   ├── registry.py          # Hook 注册表
│   └── types.py             # Hook 类型定义
├── metrics/                  # 指标系统
│   ├── __init__.py
│   ├── collector.py         # MetricsCollector
│   ├── team.py              # TeamMetrics
│   ├── performance.py      # PerformanceMetrics
│   ├── evolution.py         # EvolutionMetrics
│   ├── user.py              # UserMetrics
│   └── memory.py            # MemoryMetrics
└── cache/                    # Prompt 缓存
    ├── __init__.py
    ├── prompt.py            # PromptCache
    └── budget.py            # CacheBudgetManager
```

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **抽象封装** | 封装基础设施细节 | 便于替换和升级 |
| **统一接口** | 统一配置和调用接口 | 降低复杂度 |
| **可持久化** | 支持状态保存和恢复 | 系统可靠性 |
| **最小依赖** | 不依赖具体实现 | 灵活扩展 |

---

## 关键设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| Graph 封装 | GraphBuilder | 简化 LangGraph 使用 |
| Model 抽象层 | 多厂商支持 | 灵活切换 |
| Config 统一管理 | 集中管理 + 环境变量覆盖 | 易于维护 |
| Checkpoint 持久化 | 支持断点续连 | 系统可靠性 |
| Hook 机制 | 通用生命周期 | 统一扩展 |

---

## 参考资料

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [LangChain Chat Models](https://python.langchain.com/docs/integrations/chat/)