# UI 交互架构 - REPL 交互设计

> 版本: v1.0
> 日期: 2026-05-03
> 状态: 进行中

---

## 1. REPL 架构

```
┌─────────────────────────────────────────────────────────────┐
│                         REPL                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Input     │    │   Parser    │    │   Handler   │     │
│  │   输入      │───►│   命令解析   │───►│   命令处理   │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│                                             │              │
│                                             ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Output     │◄───│  Formatter  │◄──│   Agent     │     │
│  │   输出      │    │   格式化    │    │   执行     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   History   │    │   Config    │    │   Shortcuts │     │
│  │   历史记录   │    │   配置      │    │   快捷键   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. REPL 核心

```python
class REPL:
    """REPL 交互界面"""

    def __init__(
        self,
        agent: LeadAgent,
        session_manager: SessionManager,
        config: REPLConfig = None,
    ):
        self.agent = agent
        self.session_manager = session_manager
        self.config = config or REPLConfig()

        self._history: list[str] = []
        self._running = False

    def start(self) -> None:
        """启动 REPL"""
        self._running = True
        self._print_welcome()

        while self._running:
            try:
                user_input = self._read_input()
                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                else:
                    # 处理普通输入
                    self._handle_user_input(user_input)

            except KeyboardInterrupt:
                self._handle_interrupt()
            except EOFError:
                self._handle_eof()

        self._cleanup()

    def _read_input(self) -> str:
        """读取用户输入"""
        prompt = self._get_prompt()
        return input(prompt).strip()

    def _handle_user_input(self, user_input: str) -> None:
        """处理用户输入"""
        # 添加到历史
        self._history.append(user_input)

        # 执行
        response = await self.agent.handle(user_input)

        # 输出
        self._print_response(response)
```

---

## 3. 命令系统

```python
COMMANDS = {
    "/help": "显示帮助信息",
    "/exit": "退出 REPL",
    "/clear": "清屏",
    "/history": "显示历史记录",
    "/session": "会话管理",
    "/config": "配置管理",
    "/memory": "记忆管理",
    "/stats": "显示统计信息",
    "/compact": "压缩上下文",
}


class REPL:
    def _handle_command(self, command: str) -> None:
        """处理命令"""
        parts = command.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd == "/help":
            self._print_help()
        elif cmd == "/exit":
            self._running = False
        elif cmd == "/clear":
            self._clear_screen()
        elif cmd == "/history":
            self._print_history()
        elif cmd == "/session":
            self._handle_session(args)
        elif cmd == "/config":
            self._handle_config(args)
        elif cmd == "/memory":
            self._handle_memory(args)
        elif cmd == "/stats":
            self._print_stats()
        elif cmd == "/compact":
            self._compact_context()
        else:
            self._print_error(f"未知命令: {cmd}")

    def _print_help(self) -> None:
        """打印帮助信息"""
        lines = [
            "可用命令:",
            "",
        ]
        for cmd, desc in COMMANDS.items():
            lines.append(f"  {cmd:<15} {desc}")

        self._print("\n".join(lines))
```

---

## 4. 与 Agent 集成

```python
class REPL:
    async def _handle_user_input(self, user_input: str) -> None:
        """处理用户输入"""
        # 获取或创建会话
        session = self.session_manager.get_or_create_current()

        # 添加用户消息
        session.add_message(Message(
            role=MessageRole.USER,
            content=user_input,
        ))

        # 检查是否需要压缩
        if session.should_compact():
            self._compact_if_needed(session)

        # 执行
        response = await self.agent.handle(session)

        # 添加响应消息
        session.add_message(Message(
            role=MessageRole.ASSISTANT,
            content=response,
        ))

        # 输出
        self._print_response(response)
```

---

## 5. 与 Memory 集成

```python
class REPL:
    def _handle_memory_command(self, args: list[str]) -> None:
        """处理记忆命令"""
        memory = get_memory_layer()

        if args[0] == "list":
            memories = memory.list_all()
            self._print(memories)
        elif args[0] == "save":
            # 保存记忆
            pass
        elif args[0] == "delete":
            # 删除记忆
            pass
```

---

## 6. 相关文档

- [index.md](index.md) - UI 交互架构索引
- [cli.md](cli.md) - CLI 命令行界面
- [formatter.md](formatter.md) - 输出格式化
- [streaming.md](streaming.md) - 流式输出