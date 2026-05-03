# UI 交互架构 - CLI 命令行界面

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. CLI 架构

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  minicode [OPTIONS] [COMMAND] [ARGS]                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Options                             │   │
│  │  -m, --model MODEL    指定模型                      │   │
│  │  -c, --config FILE    指定配置文件                   │   │
│  │  -t, --thread ID      指定线程 ID                    │   │
│  │  -v, --verbose        详细输出                       │   │
│  │  --version           显示版本                       │   │
│  │  -h, --help           显示帮助                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Commands                            │   │
│  │                                                   │   │
│  │  chat     进入 REPL 交互模式                       │   │
│  │  eval     执行单条命令                             │   │
│  │  session  会话管理                                 │   │
│  │  config   配置管理                                  │   │
│  │  memory   记忆管理                                  │   │
│  │  stats    统计信息                                  │   │
│  │                                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. CLI 入口

```python
def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        prog="minicode",
        description="MiniCode - 可自我进化的多 Agent 智能终端助手",
    )

    # 全局选项
    parser.add_argument("-m", "--model", help="指定模型")
    parser.add_argument("-c", "--config", help="指定配置文件")
    parser.add_argument("-t", "--thread", help="指定线程 ID")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--version", action="version", version="1.0.0")

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # chat 子命令
    chat_parser = subparsers.add_parser("chat", help="进入 REPL 交互模式")
    chat_parser.add_argument("--no-stream", action="store_true", help="禁用流式输出")
    chat_parser.add_argument("--compact", action="store_true", help="启动时压缩上下文")

    # eval 子命令
    eval_parser = subparsers.add_parser("eval", help="执行单条命令")
    eval_parser.add_argument("command", help="要执行的命令")

    # session 子命令
    session_parser = subparsers.add_parser("session", help="会话管理")
    session_parser.add_argument("action", choices=["list", "new", "load", "delete"])

    # config 子命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("action", choices=["show", "set", "get"])

    # 解析参数
    args = parser.parse_args()

    # 执行命令
    if args.command == "chat":
        run_chat(args)
    elif args.command == "eval":
        run_eval(args)
    elif args.command == "session":
        run_session(args)
    elif args.command == "config":
        run_config(args)
    else:
        # 默认进入 REPL
        run_chat(args)


if __name__ == "__main__":
    main()
```

---

## 3. CLI 子命令实现

```python
def run_chat(args) -> None:
    """运行 REPL"""
    config = load_config(args)

    # 创建组件
    agent = create_agent(config)
    session_manager = create_session_manager(config)

    # 启动 REPL
    repl = REPL(agent, session_manager)

    if args.no_stream:
        repl.config.stream_output = False

    if args.compact:
        repl.compact_context()

    repl.start()


def run_eval(args) -> None:
    """执行单条命令"""
    config = load_config(args)
    agent = create_agent(config)

    # 执行命令
    result = await agent.handle(args.command)

    # 输出结果
    print(result)


def run_session(args) -> None:
    """会话管理"""
    session_manager = SessionManager()

    if args.action == "list":
        sessions = session_manager.list_sessions()
        print_table(sessions)
    elif args.action == "new":
        session = session_manager.create_session()
        print(f"创建会话: {session.id}")
    elif args.action == "load":
        session = session_manager.load_session(args.session_id)
        if session:
            print(f"加载会话: {session.id}")
        else:
            print(f"会话不存在: {args.session_id}")
    elif args.action == "delete":
        session_manager.delete_session(args.session_id)
        print(f"删除会话: {args.session_id}")
```

---

## 4. 配置

### 4.1 REPL 配置

```python
@dataclass
class REPLConfig:
    """REPL 配置"""
    prompt: str = ">>> "                      # 输入提示符
    stream_output: bool = True               # 流式输出
    show_time: bool = False                  # 显示时间
    show_tokens: bool = False                 # 显示 token 数
    auto_compact: bool = True                # 自动压缩
    compact_threshold: float = 0.7          # 压缩阈值
    history_size: int = 100                  # 历史记录大小
    colors: dict = field(default_factory=dict)  # 颜色配置
```

### 4.2 颜色配置

```python
DEFAULT_COLORS = {
    "prompt": "cyan",
    "user": "green",
    "assistant": "blue",
    "error": "red",
    "warning": "yellow",
    "info": "white",
    "code": "gray",
}
```

---

## 5. 相关文档

- [index.md](index.md) - UI 交互架构索引
- [repl.md](repl.md) - REPL 交互设计
- [formatter.md](formatter.md) - 输出格式化
- [streaming.md](streaming.md) - 流式输出