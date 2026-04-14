# MiniCode 架构设计

## 概述

MiniCode 是一个类 Claude Code 的终端编码助手，基于 LangGraph 构建，支持多轮对话、工具调用、团队协作等功能。

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI 层                               │
│                   (cli.py / REPL)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Agent 层                               │
│            (AgentRunner + LangGraph Workflow)                │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Services 层    │ │   Tools 层       │ │   Utils 层      │
│  (配置/会话/模型) │ │  (13类工具)      │ │  (prompt/check) │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 模块说明

### 1. CLI 层 (cli.py)

入口点，支持两种模式：
- **单命令模式**: `minicode "帮我创建文件"`
- **交互模式**: 直接运行 `minicode` 启动 REPL

### 2. Agent 层

#### AgentRunner
- 负责协调整个 agent 的执行流程
- 支持 checkpoint 恢复
- 管理会话状态

#### AgentState
LangGraph 状态定义，包含：
- `messages` - 对话历史
- `todo_items` - Todo 列表
- `task_items` - 任务列表
- `teammates` - 团队成员状态
- `pending_background_tasks` - 后台任务

#### 工作流图
```
Entry → Agent Node → [工具调用] → Agent Node → ... → End
```

### 3. Services 层

| 服务 | 职责 |
|------|------|
| ConfigManager | 应用配置管理 (JSON) |
| SessionManager | 会话管理，支持恢复 |
| ModelProvider | 模型调用抽象 |

#### ModelProvider
支持多种模型提供者：
- `anthropic` - Claude 系列
- `openai` - GPT 系列

### 4. Tools 层

#### 工具分类

| 类别 | 工具 | 说明 |
|------|------|------|
| 文件 | read_file, write_file, edit_file | 文件读写编辑 |
| Bash | bash_run, bash_check | 命令执行 |
| 搜索 | glob_tool, grep_tool | 文件搜索 |
| 任务 | TaskCreate, TaskList, TaskUpdate | 任务管理 |
| Todo | TodoWrite, TodoList, TodoComplete | Todo 管理 |
| 团队 | spawn_teammate, send_message_to_teammate | 团队协作 |
| 后台 | background_run, check_background, poll_background_results | 后台任务 |
| Cron | cron_create, cron_list, cron_delete | 定时任务 |
| Worktree | worktree_list, worktree_create, worktree_remove | Git worktree |
| MCP | mcp_connect, mcp_list, mcp_call | MCP 协议 |
| 记忆 | memory_save, memory_get, memory_list | 持久记忆 |
| 技能 | skill_list, skill_get, skill_create | 技能管理 |
| 权限 | set_permission_mode, check_permission | 权限控制 |
| 协议 | shutdown_request, plan_approval | 特殊协议 |

### 5. Utils 层

| 工具 | 说明 |
|------|------|
| SystemPromptBuilder | 动态构建系统提示 |
| CheckpointManager | 状态持久化 |

## 数据流

```
用户输入 → CLI → AgentRunner → AgentState
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ModelProvider   Tools Registry   Checkpoint
                    │              │              │
                    ▼              ▼              ▼
              LLM 响应      工具执行        状态保存
                    │              │
                    └──────────────┘
                           │
                           ▼
                     响应输出
```

## 存储结构

```
~/.mini-agent-cli/
├── config.json          # 应用配置
├── sessions/            # 会话目录
│   └── {session_id}.json
├── checkpoint.db        # Checkpoint 数据库 (可选)
├── skills/              # 技能目录
│   └── {skill_name}/
│       └── SKILL.md
└── .memory/             # 记忆目录
    ├── MEMORY.md
    └── {memory_name}.md
```

## 设计决策

1. **基于 LangGraph**: 使用图结构定义 agent 工作流，支持条件分支和循环
2. **状态持久化**: 支持会话恢复，通过 checkpoint 机制
3. **工具注册表**: 统一的工具注册机制，便于扩展
4. **服务层抽象**: 配置、会话、模型提供者解耦
5. **支持多模型**: 通过 ModelProvider 抽象支持多种 LLM

## 扩展点

1. **添加新工具**: 在 `tools/` 目录创建新工具文件，注册到 `registry.py`
2. **添加新服务**: 在 `services/` 目录创建新服务
3. **自定义工作流**: 修改 `agent/graph.py` 中的工作流定义
4. **MCP 集成**: 配置 MCP 服务器，调用 `mcp_tools`

## 依赖

- langgraph >= 0.0.20
- langchain-anthropic >= 0.1.0
- langchain-openai >= 0.0.5
- langchain-core >= 0.1.0
- click >= 8.0.0
- rich >= 13.0.0
