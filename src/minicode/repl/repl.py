"""REPL interface for interactive mode."""
import asyncio
import sys
from typing import Optional

from langchain_core.messages import HumanMessage


class REPL:
    """Interactive REPL for the agent."""

    def __init__(self, runner):
        self.runner = runner
        self.history: list[str] = []
        self.running = True

    def print_welcome(self) -> None:
        """Print welcome message."""
        print("=" * 50)
        print("MiniCode - Claude-style coding agent")
        print("=" * 50)
        print("Type your commands. Press Ctrl+C to exit.")
        print()

    def print_response(self, response: str) -> None:
        """Print agent response."""
        print("\n[Agent]")
        print(response)
        print()

    async def run(self) -> None:
        """Run the REPL loop."""
        self.print_welcome()

        while self.running:
            try:
                user_input = input("> ").strip()
                if not user_input:
                    continue

                self.history.append(user_input)

                messages = [HumanMessage(content=user_input)]

                response = await self.runner.run(messages)
                self.print_response(str(response.get("messages", [])))

            except KeyboardInterrupt:
                print("\nExiting...")
                self.running = False
            except EOFError:
                self.running = False
            except Exception as e:
                print(f"[Error] {e}")

    def stop(self) -> None:
        """Stop the REPL."""
        self.running = False


async def start_repl(runner) -> None:
    """Start the REPL."""
    repl = REPL(runner)
    await repl.run()
