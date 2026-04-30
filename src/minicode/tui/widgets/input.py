"""Input area widget for MiniCode TUI."""
import os
from pathlib import Path
from typing import Optional
from textual.message import Message
from textual.widgets import TextArea
from textual.widget import Widget


class InputArea(TextArea):
    """Custom input area with file and command completion."""

    class Submit(Message):
        """Posted when the user submits text."""
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(
        self,
        name: str = "input",
        placeholder: str = "Type your message... (@file or /command)",
    ) -> None:
        super().__init__(
            id=name,
            placeholder=placeholder,
            multiline=False,
            tab_behavior="focus",
        )
        self._history: list[str] = []
        self._history_index: int = -1

    def _on_input_changed(self, event) -> None:
        """Handle input changes for completion."""
        text = self.text
        cursor = self.cursor_position

        # @ 文件路径补全
        if text and text[cursor - 1] == "@":
            self._show_file_suggestions()

        # / 命令补全
        if text.startswith("/"):
            self._show_command_suggestions(text)

    def _show_file_suggestions(self) -> None:
        """Show file path suggestions."""
        # TODO: 实现文件路径补全
        pass

    def _show_command_suggestions(self, prefix: str) -> None:
        """Show command suggestions based on prefix."""
        commands = [
            "/help",
            "/quit",
            "/exit",
            "/clear",
            "/status",
            "/tools",
            "/tasks",
            "/todos",
            "/memory",
            "/dream",
            "/skills",
            "/team",
            "/cron",
            "/hooks",
            "/compact",
            "/stats",
            "/permission",
            "/preference",
            "/project",
        ]

        matches = [c for c in commands if c.startswith(prefix)]
        if matches:
            # TODO: 显示建议列表
            pass

    def _on_key(self, event) -> None:
        """Handle special keys."""
        from textual.keys import Keys

        # Enter 提交
        if event.key == Keys.Enter:
            text = self.text.strip()
            if text:
                self._history.append(text)
                self._history_index = len(self._history)
                self.post_message(self.Submit(text))
                self.text = ""

        # Up 上一条历史
        elif event.key == Keys.Up:
            if self._history and self._history_index > 0:
                self._history_index -= 1
                self.text = self._history[self._history_index]
                self.cursor_position = len(self.text)

        # Down 下一条历史
        elif event.key == Keys.Down:
            if self._history and self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.text = self._history[self._history_index]
                self.cursor_position = len(self.text)
            elif self._history_index == len(self._history) - 1:
                self._history_index = len(self._history)
                self.text = ""

        # Tab 尝试补全
        elif event.key == Keys.tab:
            self._handle_completion()


class InputFooter(Widget):
    """Footer with input hints and status."""

    def __init__(self) -> None:
        super().__init__()
        self.hints = "@file /cmd | Ctrl+P: 面板 | Ctrl+L: 清屏 | Ctrl+C: 取消"

    def compose(self):
        from textual.widgets import Static
        yield Static(
            f"[dim]{self.hints}[/dim]",
            markup=True,
        )