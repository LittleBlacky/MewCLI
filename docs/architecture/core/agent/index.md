# Agent 核心架构 - 文档索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **base** | `core/agent/base.md` | 核心类型定义（AgentRole、Task、Message 等） |
| **state** | `core/agent/state.md` | Agent 状态机定义 |
| **lead** | `core/agent/lead.md` | Lead Agent 实现（理解、分解、汇总） |
| **worker** | `core/agent/worker.md` | Worker Agent 实现（执行任务） |
| **protocol** | `core/agent/protocol.md` | Agent 间通信协议 |

---

## 模块结构

```
core/agent/
├── __init__.py          # 导出公共类型
├── base.py              # 核心类型定义（AgentRole、Task、Message 等）
├── state.py             # Agent 状态定义
├── lead.py              # Lead Agent 实现
├── worker.py            # Worker Agent 实现
└── protocol.py          # Agent 协作协议
```

---

## 设计原则

| 原则         | 说明                                | 原因                       |
| ------------ | ----------------------------------- | -------------------------- |
| **角色分离** | Lead Agent 和 Worker Agent 职责明确 | 便于分别优化和扩展         |
| **类型安全** | 使用 dataclass 和 Enum              | 编译期检查，减少运行时错误 |
| **可序列化** | 所有类型支持 to_dict/from_dict      | 支持持久化和状态恢复       |
| **智能分解** | 使用 LLM 动态决定任务分解策略       | 根据任务特点自适应分解     |

---

## 核心设计决策

| 设计决策               | 原因                        | 好处               |
| ---------------------- | --------------------------- | ------------------ |
| Lead/Worker 角色分离   | 不同角色职责不同            | 便于分别实现和优化 |
| Task 支持树形结构      | 子任务可能再有子任务        | 支持多级分解       |
| Message 支持 LangChain | 使用 LangGraph 作为核心框架 | 无缝集成           |
| AgentConfig 可配置     | 不同场景需要不同配置        | 灵活适应           |

---

## 相关文档

- [../infra/graph.md](../infra/graph.md) - GraphState 定义
- [../core/team/index.md](../core/team/index.md) - Team 协作架构
- [../core/session/index.md](../core/session/index.md) - Session 会话架构