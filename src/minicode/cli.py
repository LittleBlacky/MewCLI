"""CLI Entry Point - Pure terminal REPL like Claude Code."""
import sys
import os
import asyncio
from pathlib import Path
import argparse

from minicode.agent.runner import AgentRunner
from minicode.agent.session import SessionConfig


def parse_args():
    parser = argparse.ArgumentParser(
        description="MiniCode - 智能终端编码助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  minicode                          Start REPL
  minicode "fix the bug"            Run a single task
  minicode --model claude-sonnet-4-7   Use different model
  minicode --workdir /path/to/proj  Set working directory

Keyboard:
  Ctrl+C   Quit
  Ctrl+L   Clear screen
  Ctrl+D   Exit
        """,
    )
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--model", "-m", default=None, help="Model name")
    parser.add_argument("--provider", "-p", default=None, help="Model provider")
    parser.add_argument("--workdir", "-w", type=Path, help="Working directory")
    parser.add_argument("--session", "-s", default="default", help="Session ID")
    parser.add_argument("--no-checkpoint", action="store_true", help="Disable checkpoint")
    parser.add_argument("--db", help="SQLite DB path for checkpointing")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    return parser.parse_args()


# 颜色支持
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    DIM = "\033[2m"

    @classmethod
    def disable(cls) -> None:
        cls.RESET = cls.BOLD = cls.RED = cls.GREEN = ""
        cls.YELLOW = cls.BLUE = cls.MAGENTA = cls.CYAN = cls.DIM = ""


def color(text: str, color: str) -> str:
    """Colorize text."""
    return f"{color}{text}{Colors.RESET}"


def print_welcome() -> None:
    """Print welcome message."""
    print()
    print(color("  ╔══════════════════════════════════════╗", Colors.CYAN))
    print(color("  ║", Colors.CYAN) + color("        MiniCode - AI Coding Agent", Colors.BOLD + Colors.CYAN).center(36) + color("║", Colors.CYAN))
    print(color("  ╚══════════════════════════════════════╝", Colors.CYAN))
    print()
    print(f"{Colors.DIM}Type your request or press Ctrl+C to quit{Colors.RESET}")
    print(f"{Colors.DIM}Use /help for commands{Colors.RESET}")
    print()


async def run_task(runner: AgentRunner, task: str, no_color: bool = False) -> None:
    """Run a single task."""
    if no_color:
        Colors.disable()

    print(f"\n{color('[', Colors.DIM)}{color('Task', Colors.CYAN)}{color(']', Colors.DIM)} {task}\n")

    from langchain_core.messages import HumanMessage

    messages = [HumanMessage(content=task)]
    try:
        result = await runner.run(messages)
        msgs = result.get("messages", [])
        if msgs:
            last = msgs[-1]
            content = last.content if hasattr(last, "content") else str(last)
            print(f"\n{content}")
    except Exception as e:
        print(f"{color('Error:', Colors.RED)} {e}")


async def run_repl(runner: AgentRunner, no_color: bool = False) -> None:
    """Run interactive REPL."""
    if no_color:
        Colors.disable()

    print_welcome()

    messages = []
    history = []
    history_idx = -1

    while True:
        try:
            # 显示 prompt
            prompt = f"{color('>', Colors.GREEN)} "
            try:
                user_input = input(prompt)
            except (KeyboardInterrupt, EOFError):
                print(f"\n{color('Goodbye!', Colors.CYAN)}")
                break

            if not user_input.strip():
                continue

            # 处理命令
            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                args = user_input[len(cmd):].strip()

                if cmd in ("/quit", "/exit", "/q"):
                    print(f"{color('Goodbye!', Colors.CYAN)}")
                    break
                elif cmd in ("/clear", "/c"):
                    os.system("cls" if os.name == "nt" else "clear")
                    continue
                elif cmd in ("/help", "/h", "?"):
                    print_help()
                    continue
                elif cmd in ("/history", "/hist"):
                    show_history(history)
                    continue
                elif cmd in ("/permission", "/perms"):
                    show_permissions()
                    continue
                elif cmd in ("/session", "/sess"):
                    show_session(runner)
                    continue
                else:
                    print(f"{color('Unknown command:', Colors.YELLOW)} {cmd}")
                    print(f"{color('Type /help for available commands', Colors.DIM)}")
                    continue

            # 添加到历史
            history.append(user_input)
            history_idx = len(history)

            # 添加消息
            messages.append({"role": "user", "content": user_input})

            # 显示 thinking 状态
            print(f"\n{color('Thinking...', Colors.DIM)}", end="", flush=True)

            # 执行
            from langchain_core.messages import HumanMessage
            langchain_msgs = [HumanMessage(content=user_input)]

            try:
                result = await runner.run(langchain_msgs)

                # 清除 thinking
                print("\r" + " " * 20 + "\r", end="")

                # 显示响应
                msgs = result.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    content = last.content if hasattr(last, "content") else str(last)
                    print(content)

                    # 保存 assistant 响应
                    messages.append({"role": "assistant", "content": content})
                else:
                    print(f"{color('No response from agent', Colors.YELLOW)}")

            except Exception as e:
                print("\r" + " " * 20 + "\r", end="")
                print(f"{color('Error:', Colors.RED)} {e}")

        except KeyboardInterrupt:
            print(f"\n{color('(Use /quit or Ctrl+D to exit)', Colors.DIM)}")
        except EOFError:
            print(f"\n{color('Goodbye!', Colors.CYAN)}")
            break


def print_help() -> None:
    """Print help message."""
    print(f"""
{color('Commands:', Colors.BOLD + Colors.CYAN)}
  /help, /h          Show this help
  /quit, /q, /exit   Exit
  /clear, /c         Clear screen
  /history           Show command history
  /permission        Show permission rules
  /session           Show session info

{color('Tips:', Colors.BOLD + Colors.CYAN)}
  @filename          Reference a file
  Permission prompts: y (yes), a (allow type), n (no), d (deny)
""")


def show_history(history: list) -> None:
    """Show command history."""
    if not history:
        print(f"{color('No history', Colors.DIM)}")
        return
    print(f"{color('History:', Colors.CYAN)}")
    for i, h in enumerate(history[-20:], len(history) - 19):
        print(f"  {color(f'{i}.', Colors.DIM)} {h[:60]}...")


def show_permissions() -> None:
    """Show permission configuration."""
    from minicode.tools.permission_tools import get_permission_rules

    rules = get_permission_rules()
    config = rules.get("config", {})

    print(f"""
{color('Permission Configuration:', Colors.CYAN)}
  Config file: {config.get('config_path', 'N/A')}
  Loaded: {'Yes' if config.get('loaded') else 'No'}
  Allow patterns: {config.get('allow_patterns', 0)}
  Deny patterns: {config.get('deny_patterns', 0)}
  Session patterns: {config.get('session_patterns', 0)}
  Prompt threshold: {config.get('prompt_threshold', 'medium')}

{color('Built-in Dangerous Patterns:', Colors.RED)}""")

    for p in rules.get("builtin_patterns", []):
        print(f"  [{p['risk']}] {p['name']}: {p['description']}")


def show_session(runner: AgentRunner) -> None:
    """Show session info."""
    print(f"""
{color('Session:', Colors.CYAN)}
  Thread ID: {runner.thread_id}
  Workdir: {runner.workdir}
""")


async def run_single_task(runner: AgentRunner, task: str, no_color: bool = False) -> None:
    """Run a single task and exit."""
    await run_task(runner, task, no_color)


def main():
    args = parse_args()

    # 设置环境变量
    if args.provider is not None:
        os.environ["MINICODE_PROVIDER"] = args.provider
    if args.model is not None:
        os.environ["MINICODE_MODEL"] = args.model
    if args.no_color:
        Colors.disable()

    # 创建 runner
    runner = AgentRunner(
        use_checkpoint=not args.no_checkpoint,
        workdir=args.workdir,
        thread_id=args.session,
    )

    # 运行
    if args.task:
        asyncio.run(run_single_task(runner, args.task, args.no_color))
    else:
        asyncio.run(run_repl(runner, args.no_color))


if __name__ == "__main__":
    main()
