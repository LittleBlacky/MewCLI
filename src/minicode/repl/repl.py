"""REPL interface for interactive mode - Enhanced version."""
import asyncio
import sys
from typing import Optional

from langchain_core.messages import HumanMessage


class REPL:
    """Interactive REPL for the agent."""

    COMMANDS = {
        "/help": "显示帮助信息",
        "/quit": "退出程序",
        "/exit": "退出程序",
        "/clear": "清屏",
        "/stats": "查看统计",
        "/memory": "查看记忆",
        "/dream": "触发梦境整合",
        "/team": "查看团队状态",
        "/tasks": "查看任务",
        "/preference": "保存偏好 (用法: /preference <key> <value>)",
        "/project": "保存项目知识 (用法: /project <key> <value>)",
    }

    def __init__(self, runner):
        self.runner = runner
        self.history: list[str] = []
        self.running = True

    def print_welcome(self) -> None:
        """Print welcome message."""
        print("=" * 60)
        print("MiniCode - Claude-style coding agent")
        print("=" * 60)
        print("命令: /help 查看所有命令")
        print("=" * 60)

    def print_help(self) -> None:
        """Print help message."""
        print("\n可用命令:")
        for cmd, desc in self.COMMANDS.items():
            print(f"  {cmd:<15} {desc}")
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

        if cmd in ("/quit", "/exit"):
            # 退出时触发自我提升总结
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
            print("\033[2J\033[H")  # ANSI clear screen
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
            stats = self.runner.get_stats()
            teammates = stats.get("session", {}).get("teammates", [])
            if teammates:
                print("\n[团队]")
                for t in teammates:
                    print(f"  {t['name']} ({t['role']}): {'idle' if t['idle'] else 'working'}")
            else:
                print("\n[团队] 暂无成员")
            return True

        if cmd == "/tasks":
            print("\n[任务] 查看中...")
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
                user_input = input("\033[36m>>> \033[0m").strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith("/"):
                    await self.handle_command(user_input)
                    continue

                self.history.append(user_input)

                # 执行任务
                print("\n[思考中...]\n")
                messages = [HumanMessage(content=user_input)]

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
