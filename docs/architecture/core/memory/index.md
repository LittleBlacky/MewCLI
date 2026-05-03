# Memory 记忆架构 - 文档索引

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 文档索引

| 文档 | 文件路径 | 核心内容 |
|------|----------|----------|
| **index** | `memory/index.md` | 总索引 |
| **preference** | `memory/preference.md` | Preference 偏好层 |
| **knowledge** | `memory/knowledge.md` | Knowledge 知识层 |
| **episodic** | `memory/episodic.md` | Episodic 事件层 |
| **dream** | `memory/dream.md` | Dream 梦境整合 |
| **layer** | `memory/layer.md` | 记忆层整合 |

---

## 模块结构

```
core/memory/
├── __init__.py              # 导出公共类型
├── preference.py            # 用户偏好层
├── knowledge.py             # 项目知识层
├── episodic.py              # 事件记忆层
├── dream.py                 # 梦境整合层（Dream Consolidator）
└── layer.py                 # 记忆层整合
```

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **分层设计** | 三层记忆各有职责 | 便于管理 |
| **Markdown 存储** | 便于阅读和编辑 | 用户友好 |
| **按需检索** | 只在需要时检索 | 节省资源 |
| **自动注入** | 自动注入相关记忆 | 提高效率 |
| **梦境整合** | 会话间隙自动整合记忆 | 去重优化 |

---

## 三层记忆职责

| 层级 | 职责 | 生命周期 | 注入时机 |
|------|------|----------|----------|
| **Preference** | 用户偏好 | 长期 | 每次会话开始 |
| **Knowledge** | 项目知识 | 长期 | 会话开始 + 按需 |
| **Episodic** | 事件记忆 | 短期 | 按需检索 |

> **Dream 梦境整合**不是一个存储层，而是控制层，负责监控和整合以上三层记忆，在会话间隙自动触发。

---

## 存储结构

```
.minicode/
└── memory/                  # 记忆存储目录
    ├── static/                  # 静态记忆
    │   ├── preferences.md      # 用户偏好
    │   └── project.md           # 项目知识
    ├── session/                # 会话记忆
    │   └── session_{thread_id}.json
    ├── episodic/              # 事件记忆
    │   ├── episode_xxx.md
    │   └── ...
    └── .dream_lock           # 梦境整合锁（防止并发）
```

---

## 相关文档

- [../agent/index.md](../agent/index.md) - Agent 核心架构
- [../evolution/index.md](../evolution/index.md) - Evolution 进化架构
- [../../skill/index.md](../../skill/index.md) - Skill 技能系统