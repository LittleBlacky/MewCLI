# Session 会话架构 - 文档索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **index** | `core/session/index.md` | 总索引 |
| **context** | `core/session/context.md` | SessionContext、容量管理、记忆注入 |
| **manager** | `core/session/manager.md` | SessionManager、会话生命周期 |
| **checkpoint** | `core/session/checkpoint.md` | 会话断点持久化 |

---

## 模块结构

```
core/session/
├── __init__.py          # 导出公共类型
├── manager.py            # SessionManager
├── context.py            # SessionContext、SessionConfig、SessionMetrics
└── checkpoint.py         # 会话断点（可选扩展）
```

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **上下文隔离** | 每个会话有独立的上下文 | 支持多会话并发 |
| **状态持久化** | 会话状态可以保存和恢复 | 支持断点续连 |
| **容量管理** | 管理上下文长度，避免溢出 | 保证系统稳定 |
| **指标追踪** | 收集会话级指标 | 用于优化和监控 |

---

## 核心设计决策

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| Session 与 Thread 分离 | 支持多会话多线程 | 并发能力强 |
| 容量管理内嵌 | 上下文可能变得很长 | 自动触发压缩 |
| 消息历史保留 | 需要对话上下文 | 支持连续对话 |
| 指标分离 | 会话级和系统级指标不同 | 便于分析 |

---

## 相关文档

- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构
- [../core/team/index.md](../core/team/index.md) - Team 协作架构
- [../../memory/index.md](../../memory/index.md) - 记忆系统