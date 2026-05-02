"""REPL interface for interactive mode - Enhanced version with @ file and / command support."""
import asyncio
import glob
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from langchain_core.messages import HumanMessage

# Import permission system
from minicode.tools.bash_tools import set_global_permission_callback, get_bash_tools
from minicode.tools.permission_config import get_permission_config


class REPL:
    """Interactive REPL for the agent with @ file references and / command completion."""

    COMMANDS = {
        "/help": "显示帮助信息",
        "/quit": "退出程序",
        "/exit": "退出程序",
        "/clear": "清屏",
        "/status": "查看Agent状态",

        "/tools": "列出所有可用工具",
        "/permission": "管理权限 (list/allow/deny)",

        "/tasks": "查看任务列表",
        "/todos": "查看待办事项",
        "/new": "创建新任务 (用法: /new <title>)",

        "/memory": "查看记忆系统",
        "/dream": "触发梦境整合",
        "/skills": "查看技能列表",
        "/preference": "保存偏好 (用法: /preference <key> <value>)",
        "/project": "保存项目知识 (用法: /project <key> <value>)",

        "/team": "查看团队状态",
        "/teammates": "列出所有队友",
        "/spawn": "召唤新队友 (用法: /spawn <name> <role> <task>)",
        "/send": "发送消息给队友 (用法: /send <name> <message>)",
        "/inbox": "查看收件箱",
        "/pool": "管理 Agent 池 (list/run/clear)",

        "/read": "读取文件 (用法: /read <path>)",
        "/ls": "列出文件 (用法: /ls [dir])",

        "/cron": "查看定时任务",
        "/hooks": "查看钩子列表",
        "/compact": "压缩对话历史",
        "/stats": "查看统计信息",
        "/mcp": "管理 MCP 服务器 (list/add/remove)",
    }

    def __init__(self, runner):
        self.runner = runner
        self.history: list[str] = []
        self.running = True
        self.console = Console() if HAS_RICH else None
        self._file_cache: dict[str, str] = {}

        if HAS_READLINE:
            self._setup_readline()

        # Set up global permission callback for REPL
        set_global_permission_callback(self._handle_permission_prompt)

    def _handle_permission_prompt(self, command: str) -> tuple[str, str]:
        """Handle permission prompt in REPL - 同步阻塞等待.

        Returns:
            tuple of (action, pattern)
            - ("allow", "") - 允许这一次
            - ("session", pattern) - 允许同类命令
            - ("deny", "") - 拒绝这一次
            - ("permanent", pattern) - 加入永久拒绝列表
        """
        config = get_permission_config()
        allowed, reason, risk, _ = config.check(command)
        pattern = config.extract_command_type(command)

        # 颜色定义
        colors = {
            "critical": "\033[91m",
            "high": "\033[93m",
            "medium": "\033[93m",
            "low": "\033[92m",
            "none": "\033[90m",
        }
        reset = "\033[0m"
        bold = "\033[1m"

        color = colors.get(risk, "\033[93m")

        print(f"\n{bold}{color}⚠ Permission Required{reset}")
        print(f"  Command: {command}")
        print(f"  Reason:  {reason or 'Unknown command'}")
        print(f"  Risk:    {color}[{risk}]{reset}")
        print(f"  Pattern: {pattern}")
        print()
        print(f"{bold}Options:{reset}")
        print(f"  [y]  Allow this once")
        print(f"  [a]  Allow all '{pattern}' commands this session")
        print(f"  [n]  Deny this once")
        print(f"  [d]  Add to permanent deny list")
        print()

        while True:
            try:
                choice = input("Your choice (y/a/n/d): ").strip().lower()
                if choice in ("y", "yes"):
                    return ("allow", "")
                elif choice in ("a", "allow-type"):
                    # 添加到 session patterns
                    config.add_session_pattern(command)
                    return ("session", pattern)
                elif choice in ("n", "no", ""):
                    return ("deny", "")
                elif choice == "d":
                    config.add_permanent_deny(command)
                    return ("permanent", pattern)
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.")
                return ("deny", "")

    def _setup_readline(self) -> None:
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous on")

    def _completer(self, text: str, state: int) -> Optional[str]:
        if not text:
            return None

        if text.startswith("/"):
            matching = [cmd for cmd in self.COMMANDS.keys() if cmd.startswith(text)]
            if state < len(matching):
                return matching[state]
            return None

        if text.startswith("@"):
            base = text[1:]
            if "/" in base or "\\" in base:
                dir_part = os.path.dirname(base)
                pattern = os.path.basename(base) + "*"
                dir_path = Path(dir_part) if dir_part else Path.cwd()
            else:
                pattern = base + "*"
                dir_path = Path.cwd()

            matches = []
            try:
                for p in dir_path.glob(pattern):
                    if p.is_file():
                        prefix = "@" + (str(p.relative_to(Path.cwd())) if p.is_relative_to(Path.cwd()) else str(p))
                        matches.append(prefix)
                    elif p.is_dir():
                        prefix = "@" + (str(p.relative_to(Path.cwd())) if p.is_relative_to(Path.cwd()) else str(p)) + "/"
                        matches.append(prefix)
            except Exception:
                pass

            if not matches:
                try:
                    for p in Path.cwd().glob(pattern):
                        if p.is_file():
                            matches.append("@" + str(p.name))
                        elif p.is_dir():
                            matches.append("@" + str(p.name) + "/")
                except Exception:
                    pass

            if state < len(matches):
                return matches[state]
            return None

        return None

    def _expand_at_references(self, text: str) -> str:
        """展开 @ 文件引用为文件内容."""
        pattern = r'@([^\s@]+)'

        def replace_match(match):
            filepath = match.group(1)
            return self._get_file_reference(filepath)

        return re.sub(pattern, replace_match, text)

    def _get_file_reference(self, filepath: str) -> str:
        """获取文件的引用内容."""
        path = Path(filepath)
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            return f"[文件不存在: {filepath}]"

        if path.is_dir():
            return f"[目录: {filepath}]"

        try:
            cache_key = str(path)
            if cache_key in self._file_cache:
                return self._file_cache[cache_key]

            content = path.read_text(encoding="utf-8")
            max_lines = 100
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n... (共 {len(lines)} 行，省略 {len(lines) - max_lines} 行)"

            ref = f"\n[文件: {filepath}]\n```\n{content}\n```\n"
            self._file_cache[cache_key] = ref
            return ref
        except Exception as e:
            return f"[读取文件失败: {filepath} - {e}]"

    def _preview_file(self, filepath: str) -> str:
        """预览文件内容."""
        path = Path(filepath)
        if not path.exists():
            return f"文件不存在: {filepath}"
        if path.is_dir():
            return f"是目录: {filepath}"

        try:
            lines = path.read_text(encoding="utf-8").split("\n")
            total = len(lines)
            preview = "\n".join(lines[:20])
            if total > 20:
                preview += f"\n... (+{total - 20} 行)"
            return preview
        except Exception as e:
            return f"读取失败: {e}"

    def _get_prompt(self) -> str:
        """获取带样式的提示符."""
        if self.console:
            return "[cyan]>>>[/cyan] "
        return ">>> "

    def print_welcome(self) -> None:
        """Print welcome message."""
        if self.console:
            self.console.print(Panel.fit(
                "[bold cyan]MiniCode[/bold cyan] - 终端编码助手\n"
                "[dim]支持 @文件 引用和 /命令 快捷操作[/dim]",
                border_style="cyan"
            ))
            print()
            self.console.print("[dim]提示:[/dim] [cyan]@文件名[/cyan] 引用文件  [cyan]/[/cyan] 查看命令  [cyan]/help[/cyan] 帮助")
            print()
        else:
            print("=" * 60)
            print("MiniCode - Claude-style coding agent")
            print("=" * 60)
            print("@文件名 - 引用文件内容")
            print("/       - 查看所有命令")
            print("/help    - 获取帮助")
            print("=" * 60)

    def print_help(self) -> None:
        """Print help message."""
        if self.console:
            table = Table(title="可用命令", show_lines=True)
            table.add_column("命令", style="cyan", no_wrap=True)
            table.add_column("描述", style="white")

            for cmd, desc in self.COMMANDS.items():
                table.add_row(cmd, desc)

            print()
            self.console.print(table)
            print()
        else:
            print("\n可用命令:")
            for cmd, desc in self.COMMANDS.items():
                print(f"  {cmd:<15} {desc}")
            print()

    def print_command_list(self) -> None:
        """Print command list when user types /."""
        if self.console:
            table = Table(title="命令列表", show_header=True)
            table.add_column("命令", style="cyan", width=20)
            table.add_column("描述", style="white")

            for cmd, desc in self.COMMANDS.items():
                table.add_row(cmd, desc)

            print()
            self.console.print(table)
            print()
        else:
            print("\n命令列表:")
            for cmd, desc in self.COMMANDS.items():
                print(f"  {cmd:<15} {desc}")
            print()

    def _do_ls(self, path: str = ".") -> None:
        """列出目录文件."""
        try:
            p = Path(path) if Path(path).is_absolute() else Path.cwd() / path
            if not p.exists():
                print(f"目录不存在: {path}")
                return

            items = list(p.iterdir())
            items.sort(key=lambda x: (not x.is_file(), x.name))

            if self.console:
                table = Table(title=f"[cyan]{p}[/cyan]")
                table.add_column("名称", style="white")
                table.add_column("类型", style="dim")
                for item in items[:20]:
                    if item.is_dir():
                        table.add_row(f"[blue]{item.name}/[/blue]", "目录")
                    else:
                        table.add_row(f"[green]{item.name}[/green]", "文件")
                print()
                self.console.print(table)
            else:
                print(f"\n{p}")
                for item in items[:20]:
                    if item.is_dir():
                        print(f"  [DIR]  {item.name}")
                    else:
                        print(f"         {item.name}")
            if len(items) > 20:
                print(f"\n... 共 {len(items)} 项")
            print()
        except Exception as e:
            print(f"错误: {e}")

    def _do_new_task(self, title: str) -> None:
        """创建新任务."""
        if not title:
            print("[用法] /new <任务标题>")
            return

        from minicode.tools.task_tools import TaskManager
        tm = TaskManager()
        task = tm.create(title, "")
        print(f"[新建任务] {title}")
        print(f"  ID: {task['id']}")
        print()

    def _do_read(self, filepath: str) -> None:
        """读取文件预览."""
        if not filepath:
            print("[用法] /read <文件路径>")
            return
        print(f"\n[文件预览] {filepath}")
        preview = self._preview_file(filepath)
        print(preview[:500])
        print()

    def print_status(self) -> None:
        """Print agent status."""
        stats = self.runner.get_stats()
        print("\n[状态]")
        print(f"  会话ID: {self.runner.thread_id}")
        print(f"  模型: {self.runner.model_name}")
        print(f"  提供商: {self.runner.model_provider}")
        print(f"  总Turns: {stats['session']['total_turns']}")
        print(f"  任务统计: {stats['self_improve']['total_tasks']} 个")
        print()

    def print_tools(self) -> None:
        """Print available tools."""
        from minicode.tools.registry import ALL_TOOLS
        print(f"\n[可用工具] {len(ALL_TOOLS)} 个")
        for i, tool in enumerate(ALL_TOOLS, 1):
            print(f"  {i:>2}. {tool.name}")
        print()

    def print_permission(self, args: str = "") -> None:
        """Print or modify permissions."""
        parts = args.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        config = get_permission_config()
        summary = config.get_config_summary()

        if action == "" or action == "status":
            print("\n[权限状态]")
            print(f"  配置文件: {summary['config_path'] or '未加载'}")
            print(f"  已加载: {'是' if summary['loaded'] else '否'}")
            print(f"  用户允许规则: {summary['allow_patterns']} 个")
            print(f"  用户拒绝规则: {summary['deny_patterns']} 个")
            print(f"  永久拒绝规则: {summary['permanent_deny_patterns']} 个")
            print(f"  会话允许规则: {summary['session_patterns']} 个")
            print(f"  提示未知命令: {summary['prompt_unknown']}")
            print(f"  提示阈值: {summary['prompt_threshold']}")
            print(f"  内置危险规则: {summary['builtin_patterns']} 个")
            print()
            print("  子命令:")
            print("    /permission list         - 列出所有规则")
            print("    /permission session      - 列出会话规则")
            print("    /permission deny         - 列出永久拒绝规则")
            print("    /permission clear        - 清除会话规则")
            print("    /permission allow <cmd>  - 添加允许规则")
            print()
            return

        if action == "list":
            print("\n[权限规则]")
            # 内置危险规则
            builtin = config.get_builtin_patterns()
            print(f"\n  内置危险规则 ({len(builtin)}):")
            for p in builtin:
                print(f"    [{p['risk']}] {p['name']}: {p['description']}")

            # 用户允许规则
            if summary['allow_patterns'] > 0:
                print(f"\n  用户允许规则 ({summary['allow_patterns']}):")

            # 用户拒绝规则
            if summary['deny_patterns'] > 0:
                print(f"\n  用户拒绝规则 ({summary['deny_patterns']}):")

            # 永久拒绝规则
            permanent = config.get_permanent_deny_patterns()
            if permanent:
                print(f"\n  永久拒绝规则 ({len(permanent)}):")
                for p in permanent:
                    print(f"    - {p}")
            print()
            return

        if action == "session":
            patterns = config.get_session_patterns()
            print("\n[会话允许规则]")
            if not patterns:
                print("  暂无会话规则")
                print("  使用 [a] 选项添加: 允许同类命令在当前会话中无需确认")
            else:
                print(f"  共 {len(patterns)} 条规则:")
                for p in patterns:
                    print(f"    - {p}")
            print()
            return

        if action == "deny":
            patterns = config.get_permanent_deny_patterns()
            print("\n[永久拒绝规则]")
            if not patterns:
                print("  暂无永久拒绝规则")
            else:
                print(f"  共 {len(patterns)} 条规则:")
                for p in patterns:
                    print(f"    - {p}")
            print()
            return

        if action == "clear":
            count = len(config.get_session_patterns())
            config.clear_session_patterns()
            print(f"\n[清除] 已清除 {count} 条会话规则")
            print()
            return

        if action == "allow":
            if not rest:
                print("\n[用法] /permission allow <command>")
                print("  示例: /permission allow rm -rf")
                print()
                return
            pattern = config.extract_command_type(rest)
            config._allow_patterns.append((pattern, "glob", config._glob_to_regex(pattern)))
            print(f"\n[添加] 已添加允许规则: {pattern}")
            print()
            return

        if action == "remove":
            if not rest:
                print("\n[用法] /permission remove <pattern>")
                print()
                return
            if config.remove_permanent_deny(rest):
                print(f"\n[移除] 已从永久拒绝列表移除: {rest}")
            else:
                print(f"\n[未找到] 模式不存在: {rest}")
            print()
            return

        # Unknown action
        print(f"\n[权限] 未知命令: {action}")
        print("  用法: /permission [status|list|session|deny|clear|allow|remove]")
        print()

    def print_todos(self) -> None:
        """Print todo list."""
        mem = self.runner.get_memory()
        todos = mem['session'].get('pending', [])
        if not todos:
            print("\n[待办] 暂无待办事项")
        else:
            print(f"\n[待办] {len(todos)} 项")
            for todo in todos:
                print(f"  • {todo}")
        print()

    def print_skills(self) -> None:
        """Print skill list."""
        from minicode.tools.skill_tools import SkillManager
        sm = SkillManager()
        skills = sm.list()
        if not skills:
            print("\n[技能] 暂无注册技能")
        else:
            print(f"\n[技能] {len(skills)} 个")
            for skill in skills:
                print(f"  • {skill['name']}: {skill['description']}")
        print()

    def print_cron(self) -> None:
        """Print cron jobs."""
        from minicode.tools.cron_tools import CronScheduler
        cs = CronScheduler()
        jobs = cs.list()
        if not jobs:
            print("\n[Cron] 暂无定时任务")
        else:
            print(f"\n[Cron] {len(jobs)} 个任务")
            for job in jobs:
                print(f"  • {job['id']}: {job.get('task', 'N/A')}")
        print()

    def do_team(self) -> None:
        """Handle team commands."""
        from minicode.tools.team_tools import get_teammate_manager, get_message_bus

        mgr = get_teammate_manager()
        bus = get_message_bus()

        teammates = mgr.list_teammates()
        print("\n[团队]")

        if not teammates:
            print("  暂无队友")
            print("\n  使用 /spawn <name> <role> <task> 召唤新队友")
        else:
            print(f"  队友数量: {len(teammates)}")
            for tm in teammates:
                status = "空闲" if tm.get("status") == "idle" else "工作中"
                print(f"  - {tm['name']} ({tm['role']}) [{status}]")

        inbox = bus._load_inbox()
        unread = sum(len(msgs) for msgs in inbox.values())
        if unread > 0:
            print(f"\n  未读消息: {unread} 条 (使用 /inbox 查看)")

        print()

    def do_teammates(self) -> None:
        """List all teammates."""
        from minicode.tools.team_tools import get_teammate_manager

        mgr = get_teammate_manager()
        teammates = mgr.list_teammates()

        if not teammates:
            print("\n[队友] 暂无队友")
            print("  使用 /spawn <name> <role> <task> 召唤新队友")
        else:
            print(f"\n[队友] {len(teammates)} 个")
            for tm in teammates:
                print(f"  - {tm['name']}: {tm['role']} (状态: {tm.get('status', 'unknown')})")
        print()

    def do_spawn(self, args: str = "") -> None:
        """Spawn a new teammate."""
        parts = args.split(maxsplit=2)

        if len(parts) < 3:
            print("\n[召唤] 用法: /spawn <name> <role> <task>")
            print("  示例: /spawn coder 前端开发 实现用户登录页面")
            print("  示例: /spawn reviewer 代码审查 审查登录模块代码")
            print()
            return

        name, role, task = parts[0], parts[1], parts[2]

        from minicode.tools.team_tools import get_teammate_manager
        mgr = get_teammate_manager()

        tm = mgr.spawn(name, role, task)
        print(f"\n[召唤] 成功创建队友 {name}")
        print(f"  角色: {role}")
        print(f"  任务: {task}")
        print(f"  状态: {tm['status']}")
        print("\n使用 /send <name> <message> 发送消息给队友")
        print()

    def do_send(self, args: str = "") -> None:
        """Send message to a teammate."""
        parts = args.split(maxsplit=1)

        if len(parts) < 2:
            print("\n[发送] 用法: /send <name> <message>")
            print("  示例: /send coder 开始实现登录功能")
            print()
            return

        name, message = parts[0], parts[1]

        from minicode.tools.team_tools import get_message_bus
        bus = get_message_bus()

        result = bus.send(name, message)
        print(f"\n{result}")
        print()

    def do_inbox(self) -> None:
        """Read inbox messages."""
        from minicode.tools.team_tools import get_message_bus

        bus = get_message_bus()
        messages = bus.read_inbox("main")

        print(f"\n{messages}")
        print()

    def do_pool(self, args: str = "") -> None:
        """Manage agent pool."""
        parts = args.split(maxsplit=1)
        action = parts[0].lower() if parts else ""

        from minicode.agent.subagent import SubAgentPool

        global _subagent_pool
        if '_subagent_pool' not in globals():
            globals()['_subagent_pool'] = SubAgentPool(max_agents=5)

        pool = globals()['_subagent_pool']

        if action == "" or action == "list":
            print(f"\n[Agent 池]")
            print(f"  最大代理数: {pool.max_agents}")
            print(f"  当前代理数: {len(pool.agents)}")
            if pool.agents:
                for agent in pool.agents:
                    print(f"  - {agent.name}: {agent.role}")
            print("\n  用法:")
            print("    /pool list      - 列出代理")
            print("    /pool run <name> <role> <task>")
            print("                  - 创建并运行子代理")
            print("    /pool clear     - 清空代理池")
            print()
            return

        if action == "run":
            if len(parts) < 2:
                print("\n[池] 用法: /pool run <name> <role> <task>")
                print("  示例: /pool run coder 前端 实现登录页面")
                print()
                return

            sub_parts = parts[1].split(maxsplit=2)
            if len(sub_parts) < 3:
                print("\n[池] 参数不足: /pool run <name> <role> <task>")
                print()
                return

            name, role, task = sub_parts[0], sub_parts[1], sub_parts[2]

            print(f"\n[池] 创建子代理 {name}...")
            agent = pool.create(name, role, task)

            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(run_agent())
            except RuntimeError:
                asyncio.new_event_loop().run_until_complete(run_agent())
            print()
            return

        if action == "clear":
            pool.clear()
            print("\n[池] 已清空")
            print()
            return

        print(f"\n[池] 未知命令: {action}")
        print("  用法: /pool [list|run|clear]")
        print()

    def print_hooks(self) -> None:
        """Print hook list."""
        from minicode.tools.hook_tools import HookManager
        hm = HookManager()
        hooks = hm.list_hooks()
        if not hooks or all(not v for v in hooks.values()):
            print("\n[钩子] 暂无活跃钩子")
        else:
            print(f"\n[钩子]")
            for hook_type, hook_list in hooks.items():
                if hook_list:
                    print(f"  {hook_type}: {len(hook_list)} 个")
                    for h in hook_list:
                        print(f"    • {h}")
        print()

    def do_compact(self) -> None:
        """Compact conversation history."""
        from minicode.tools.compact_tools import compact_history
        result = compact_history.invoke({"keep_recent": 3})
        print(f"\n[压缩] {result}")
        print()

    def do_mcp(self, args: str = "") -> None:
        """Handle MCP commands."""
        parts = args.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        from minicode.tools.mcp_tools import get_mcp_client, mcp_connect, mcp_disconnect

        client = get_mcp_client()

        if action == "" or action == "list":
            servers = client.list_servers()
            if not servers:
                print("\n[MCP] 暂无已配置的服务器")
                print("  用法: /mcp add <name> <transport> <command> [args]")
                print("  示例: /mcp add filesystem stdio npx -y @modelcontextprotocol/server-filesystem /path")
            else:
                print(f"\n[MCP] 已配置服务器 ({len(servers)}):")
                for srv in servers:
                    print(f"  - {srv['name']} ({srv['config'].get('transport', 'unknown')})")
                tools = client.get_tools()
                if tools:
                    print(f"\n[MCP] 可用工具 ({len(tools)}):")
                    for t in tools[:10]:
                        print(f"  - {t.name}")
                    if len(tools) > 10:
                        print(f"  ... 还有 {len(tools) - 10} 个")
            print()
            return

        if action == "add":
            if not rest:
                print("\n[MCP] 用法: /mcp add <name> <transport> <command> [cmd_args]")
                print("  示例: /mcp add filesystem stdio npx -y @modelcontextprotocol/server-filesystem C:/Temp")
                print("  示例: /mcp add github stdio npx -y @modelcontextprotocol/server-github")
                print()
                return

            sub_parts = rest.split()
            if len(sub_parts) < 3:
                print("\n[MCP] 参数不足，需要: <name> <transport> <command> [cmd_args]")
                print("  示例: /mcp add filesystem stdio npx -y @modelcontextprotocol/server-filesystem C:/Temp")
                print()
                return

            name = sub_parts[0]
            transport = sub_parts[1]
            command = sub_parts[2]
            cmd_args = " ".join(sub_parts[3:]) if len(sub_parts) > 3 else ""

            print(f"\n[MCP] 连接 {name}...")
            result = mcp_connect.invoke({
                "server_name": name,
                "transport": transport,
                "command": command,
                "cmd_args": cmd_args,
                "env": "{}",
                "url": "",
            })
            print(f"  {result}")

            client.refresh()
            tools = client.get_tools()
            if tools:
                print(f"\n[MCP] 已连接！可用工具 ({len(tools)}):")
                for t in tools[:10]:
                    print(f"  - {t.name}")
                if len(tools) > 10:
                    print(f"  ... 还有 {len(tools) - 10} 个")
            print()
            return

        if action == "remove" or action == "disconnect":
            if not rest:
                print("\n[MCP] 用法: /mcp remove <name>")
                print("  示例: /mcp remove github")
                print()
                return

            print(f"\n[MCP] 断开 {rest}...")
            result = mcp_disconnect.invoke({"server_name": rest})
            print(f"  {result}")
            print()
            return

        if action == "refresh":
            print("\n[MCP] 刷新工具列表...")
            count = client.refresh()
            print(f"  已刷新，{count} 个工具可用")
            print()
            return

        if action == "help":
            print("\n[MCP] 可用命令:")
            print("  /mcp list        - 列出已配置的服务器")
            print("  /mcp add <name> <transport> <command> [cmd_args]")
            print("                  - 添加并连接 MCP 服务器")
            print("  /mcp remove <name> - 断开并移除服务器")
            print("  /mcp refresh     - 刷新工具列表")
            print("\n示例:")
            print("  /mcp add filesystem stdio npx -y @modelcontextprotocol/server-filesystem C:/Temp")
            print("  /mcp add github stdio npx -y @modelcontextprotocol/server-github")
            print()
            return

        print(f"\n[MCP] 未知命令: {action}")
        print("  用法: /mcp [list|add|remove|refresh|help]")
        print()

    def print_response(self, messages: list) -> None:
        """Print agent response."""
        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                print(f"\n[Agent]\n{msg.content}\n")

    def print_stats(self) -> None:
        """Print agent stats."""
        stats = self.runner.get_stats()
        print("\n[统计]")
        print(f"  总任务: {stats['self_improve']['total_tasks']}")
        print(f"  成功: {stats['self_improve']['success_count']}")
        print(f"  失败: {stats['self_improve']['failure_count']}")
        print(f"  自我提升触发: {stats['self_improve']['improvements_triggered']}")
        print()

    def print_memory(self) -> None:
        """Print memory status."""
        mem = self.runner.get_memory()
        print("\n[记忆状态]")
        print(f"  静态技能: {mem['static']['skills_count']}")
        print(f"  动态待办: {len(mem['session']['pending'])}")
        print(f"  事件记忆: {len(mem['episodic'])}")
        print()

    async def handle_command(self, cmd: str) -> bool:
        """Handle special command. Returns True if handled."""
        cmd = cmd.strip()

        # / 单独显示命令列表
        if cmd == "/":
            self.print_command_list()
            return True

        if cmd in ("/quit", "/exit"):
            result = self.runner.on_exit()
            if result.get("patterns") or result.get("suggestions"):
                print("\n[退出总结]")
                for p in result.get("patterns", []):
                    print(f"  - {p}")
                for s in result.get("suggestions", []):
                    print(f"  建议: {s}")
            print("再见!")
            self.running = False
            return True

        if cmd == "/help":
            self.print_help()
            return True

        if cmd == "/clear":
            if self.console:
                self.console.clear()
            else:
                print("\033[2J\033[H")
            self.print_welcome()
            return True

        if cmd == "/stats":
            self.print_stats()
            return True

        if cmd == "/memory":
            self.print_memory()
            return True

        if cmd == "/dream":
            result = self.runner.trigger_dream()
            print("\n[梦境整合]")
            print(f"  模式: {len(result.get('patterns', []))}")
            print(f"  建议: {len(result.get('suggestions', []))}")
            print(f"  创建技能: {len(result.get('created_skills', []))}")
            return True

        if cmd == "/team":
            from minicode.tools.team_tools import get_teammate_manager
            tm = get_teammate_manager()
            members = tm.list_teammates()
            if members:
                print("\n[团队]")
                for m in members:
                    print(f"  {m.get('name', 'anonymous')} ({m.get('role', 'member')})")
            else:
                print("\n[团队] 暂无成员")
            return True

        if cmd == "/tasks":
            from minicode.tools.task_tools import TaskManager
            tm = TaskManager()
            tasks = tm.list_all()
            if not tasks:
                print("\n[任务] 暂无任务")
            else:
                print(f"\n[任务] {len(tasks)} 个")
                for t in tasks:
                    status = t.get('status', 'pending')
                    subject = t.get('subject', 'N/A')
                    print(f"  [{status}] {subject}")
            return True

        if cmd.startswith("/new"):
            args = cmd[4:].strip()
            self._do_new_task(args)
            return True

        if cmd == "/todos":
            self.print_todos()
            return True

        if cmd == "/status":
            self.print_status()
            return True

        if cmd == "/tools":
            self.print_tools()
            return True

        if cmd.startswith("/permission"):
            # Handle both /permission and /permission <args>
            args = cmd[11:].strip()  # Strip "/permission" prefix
            self.print_permission(args)
            return True

        if cmd == "/skills":
            self.print_skills()
            return True

        if cmd == "/cron":
            self.print_cron()
            return True

        if cmd == "/hooks":
            self.print_hooks()
            return True

        if cmd.startswith("/mcp"):
            args = cmd[4:].strip()
            self.do_mcp(args)
            return True

        if cmd == "/team":
            self.do_team()
            return True

        if cmd == "/teammates":
            self.do_teammates()
            return True

        if cmd.startswith("/spawn"):
            args = cmd[7:].strip()
            self.do_spawn(args)
            return True

        if cmd.startswith("/send"):
            args = cmd[6:].strip()
            self.do_send(args)
            return True

        if cmd == "/inbox":
            self.do_inbox()
            return True

        if cmd.startswith("/pool"):
            args = cmd[5:].strip()
            self.do_pool(args)
            return True

        if cmd == "/compact":
            self.do_compact()
            return True

        if cmd.startswith("/read"):
            args = cmd[5:].strip()
            self._do_read(args)
            return True

        if cmd.startswith("/ls"):
            args = cmd[3:].strip() or "."
            self._do_ls(args)
            return True

        if cmd.startswith("/preference "):
            parts = cmd.split(maxsplit=2)
            if len(parts) >= 3:
                self.runner.save_preference(parts[1], parts[2])
                print(f"[偏好已保存] {parts[1]}")
            else:
                print("[用法] /preference <key> <value>")
            return True

        if cmd.startswith("/project "):
            parts = cmd.split(maxsplit=2)
            if len(parts) >= 3:
                self.runner.save_project_knowledge(parts[1], parts[2])
                print(f"[项目知识已保存] {parts[1]}")
            else:
                print("[用法] /project <key> <value>")
            return True

        return False

    async def run(self) -> None:
        """Run the REPL loop."""
        self.print_welcome()

        while self.running:
            try:
                prompt = self._get_prompt()
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                    continue

                if "@" in user_input:
                    files = re.findall(r'@([^\s]+)', user_input)
                    if files:
                        print(f"[引用了 {len(files)} 个文件]")

                self.history.append(user_input)

                expanded = self._expand_at_references(user_input)

                print("\n[思考中...]\n")
                messages = [HumanMessage(content=expanded)]

                try:
                    result = await self.runner.run(messages)
                    self.print_response(result.get("messages", []))
                except Exception as e:
                    print(f"\n[错误] {e}")

            except KeyboardInterrupt:
                print("\n使用 /quit 退出")
            except EOFError:
                break
            except Exception as e:
                print(f"[错误] {e}")

    def stop(self) -> None:
        """Stop the REPL."""
        self.running = False


async def start_repl(runner) -> None:
    """Start the REPL."""
    repl = REPL(runner)
    await repl.run()
