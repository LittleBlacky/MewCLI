# Team 协作架构 - 文档索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **index** | `core/team/index.md` | 总索引 |
| **manager** | `core/team/manager.md` | TeamManager、Worker Pool、任务分配 |
| **inbox** | `core/team/inbox.md` | Inbox 消息机制 |

---

## 模块结构

```
core/team/
├── __init__.py          # 导出公共类型
├── manager.py           # TeamManager
├── inbox.py             # Inbox、InboxMessage、WorkerInfo
└── protocol.py          # 协作协议
```

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **异步协作** | 使用异步机制实现多 Agent 协作 | 提高并行效率 |
| **集中管理** | TeamManager 统一管理所有 Worker | 便于协调和监控 |
| **消息驱动** | 通过 Inbox 实现 Agent 间通信 | 解耦 Agent |
| **负载均衡** | 动态分配任务，平衡 Worker 负载 | 提高资源利用率 |

---

## 核心设计决策

| 设计决策 | 原因 | 好处 |
|----------|------|------|
| TeamManager 集中管理 | 统一协调避免冲突 | 便于监控和调度 |
| Inbox 消息机制 | 解耦 Agent 通信 | 易于扩展和测试 |
| Worker 心跳机制 | 检测 Worker 存活状态 | 自动故障恢复 |
| 任务队列 | 处理 Worker 不足的情况 | 提高系统容错性 |

---

## 相关文档

- [../core/agent/index.md](../core/agent/index.md) - Agent 核心架构
- [../core/session/index.md](../core/session/index.md) - Session 会话架构