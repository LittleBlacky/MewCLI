"""Message bubble and list widgets for MiniCode TUI."""
from typing import Optional
from textual.message import Message
from textual.widget import Widget
from textual.widgets._static import Static
from rich.text import Text
from rich.panel import Panel
from rich.box import ROUNDED

from minicode.tui.render import render_markdown, highlight_code, render_content


class MessageBubble(Widget):
    """A message bubble widget with rich text support."""

    class Changed(Message):
        """Called when the message is clicked."""
        pass

    def __init__(
        self,
        content: str,
        sender: str = "user",
        message_id: str = "",
        expand: bool = True,
    ) -> None:
        super().__init__()
        self.content = content
        self.sender = sender
        self.message_id = message_id
        self.expand = expand

    def compose(self):
        # 根据发送者选择样式
        if self.sender == "user":
            border_style = "cyan"
            title = "[cyan]You[/cyan]"
            title_align = "right"
        else:
            border_style = "green"
            title = "[green]MiniCode[/green]"
            title_align = "left"

        # 渲染内容
        try:
            rendered = self._render_content()
        except Exception:
            rendered = Text(self.content)

        yield Static(
            rendered,
            markup=True,
        )

    def _render_content(self) -> Text:
        """Render message content with syntax highlighting."""
        content = self.content

        # 如果是代码块
        if content.startswith("```") and "```" in content[3:]:
            parts = content.split("```")
            if len(parts) >= 3:
                lang = parts[1].strip() if parts[1].strip() else "text"
                code = parts[2].strip()
                syntax = highlight_code(code, lang)
                return syntax

        # 如果包含代码块
        if "```" in content:
            return render_content(content)

        # 纯 Markdown
        return render_markdown(content)

    def on_click(self) -> None:
        self.post_message(self.Changed(self))


class MessageList(Widget):
    """A scrollable list of message bubbles."""

    def __init__(self, name: str = "messages") -> None:
        super().__init__(name=name)
        self._messages: list[dict] = []

    def add_message(
        self,
        content: str,
        sender: str = "user",
        message_id: str = "",
    ) -> None:
        """Add a message to the list."""
        msg = {
            "content": content,
            "sender": sender,
            "message_id": message_id or f"msg_{len(self._messages)}",
        }
        self._messages.append(msg)
        self.refresh()

    def clear(self) -> None:
        """Clear all messages."""
        self._messages = []
        self.refresh()

    def watch_content(self) -> None:
        """Update display when messages change."""
        # Placeholder for reactive updates
        pass


class ToolCallWidget(Static):
    """Display a tool call with its result."""

    def __init__(
        self,
        tool_name: str,
        args: str = "",
        result: str = "",
        success: bool = True,
    ) -> None:
        content = f"[bold cyan]{tool_name}[/bold cyan]"
        if args:
            content += f"\n[dim]{args}[/dim]"
        if result:
            if success:
                content += f"\n\n{result}"
            else:
                content += f"\n\n[red]{result}[/red]"

        style = "green" if success else "red"
        super().__init__(
            Text.from_markup(content),
            markup=True,
        )