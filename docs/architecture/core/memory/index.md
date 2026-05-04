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
├── dream.py                 # 梦境整合层
└── layer.py                 # 记忆层整合
```

---

## 设计原则

| 原则 | 说明 | 原因 |
|------|------|------|
| **分层设计** | 三层记忆各有职责 | 便于管理 |
| **Markdown 存储** | 便于阅读和编辑 | 用户友好 |
| **LLM 检索** | 语义理解用户意图 | 智能匹配 |
| **直接读取** | Preference/Knowledge 量少，直接获取 | 节省资源 |
| **梦境整合** | 会话间隙自动整合记忆 | 去重优化 |

---

## 三层记忆职责

| 层级 | 职责 | 操作 | 检索方式 |
|------|------|------|----------|
| **Preference** | 用户偏好 | save/get/update/delete/list | 直接获取 |
| **Knowledge** | 项目知识 | save/get/update/delete/list | 直接获取 |
| **Episodic** | 事件记忆 | save/get/delete/search/consolidate | LLM 检索 |

---

## 操作总览

| 操作 | Preference | Knowledge | Episodic |
|------|-----------|-----------|----------|
| **存入** | ✅ save | ✅ save | ✅ save |
| **读取** | ✅ get/get_all | ✅ get/get_all | ✅ get/get_all |
| **检索** | ❌ | ❌ | ✅ search（LLM） |
| **更新** | ✅ update | ✅ update | ❌ 很少更新 |
| **删除** | ✅ delete | ✅ delete | ✅ delete |
| **整合** | ❌ | ❌ | ✅ consolidate（Dream） |

---

## 存储结构

```
.minicode/
└── memory/
    ├── static/
    │   ├── preferences.md     # 用户偏好
    │   └── project.md         # 项目知识
    ├── episodic/              # 事件记忆
    │   ├── episode_xxx.md
    │   └── ...
    └── .dream_lock           # 梦境整合锁
```

---

## 检索流程

```
用户输入
    │
    ▼
Preference → 直接获取（量少）
    │
Knowledge → 直接获取（量少）
    │
Episodic → LLM 语义检索（量大）
    │
    ▼
返回相关记忆
```

---

## 相关文档

- [../agent/index.md](../agent/index.md) - Agent 核心架构
- [../evolution/index.md](../evolution/index.md) - Evolution 进化架构
- [../../skill/index.md](../../skill/index.md) - Skill 技能系统