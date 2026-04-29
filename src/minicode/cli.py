"""CLI Entry Point"""
import sys
import asyncio
from pathlib import Path
import argparse

from minicode.agent.runner import AgentRunner, run_interactive
from minicode.agent.session import SessionConfig


def parse_args():
    parser = argparse.ArgumentParser(
        description="MiniCode - Claude-style coding agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  minicode --help                    Show this help
  minicode --task "fix the bug"     Run a single task
  minicode --interactive            Start interactive REPL
  minicode --model claude-3-opus    Use different model
  minicode --workdir /path/to/proj   Set working directory
        """,
    )
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive mode")
    parser.add_argument("--model", "-m", default="claude-sonnet-4-7", help="Model name (default: claaude-sonnet-4-7)")
    parser.add_argument("--provider", "-p", default="anthropic", help="Model provider (default: anthropic)")
    parser.add_argument("--workdir", "-w", type=Path, help="Working directory")
    parser.add_argument("--session", "-s", default="default", help="Session ID")
    parser.add_argument("--no-checkpoint", action="store_true", help="Disable checkpoint")
    parser.add_argument("--db", help="SQLite DB path for checkpointing")
    return parser.parse_args()


async def run_task(runner: AgentRunner, task: str) -> None:
    """Run a single task."""
    from langchain_core.messages import HumanMessage

    print(f"\n[会话: {runner.thread_id}] {task}\n")

    messages = [HumanMessage(content=task)]
    result = await runner.run(messages)

    # Print last assistant message
    msgs = result.get("messages", [])
    for msg in reversed(msgs):
        if hasattr(msg, "content") and msg.content:
            print(f"\n{msg.content}")
            break


def main():
    args = parse_args()

    # Interactive mode
    if args.interactive or not args.task:
        print("Starting MiniCode Interactive Mode...")
        print(f"Model: {args.model}")
        print("Commands: /help, /stats, /memory, /dream, /quit")
        print("-" * 50)

        asyncio.run(run_interactive(
            model_provider=args.provider,
            model_name=args.model,
            thread_id=args.session,
        ))
        return

    # Single task mode
    runner = AgentRunner(
        model_provider=args.provider,
        model_name=args.model,
        use_checkpoint=not args.no_checkpoint,
        db_path=args.db,
        workdir=args.workdir,
        thread_id=args.session,
    )

    asyncio.run(run_task(runner, args.task))


if __name__ == "__main__":
    main()
