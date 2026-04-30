"""Status bar widget for MiniCode TUI."""
from textual.widgets import StatusBar as TextualStatusBar
from textual.widgets import Static
from textual.widget import Widget


class TUIStatusBar(TextualStatusBar):
    """Custom status bar for MiniCode."""

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-7",
        session_id: str = "default",
    ) -> None:
        super().__init__()
        self.model_name = model_name
        self.session_id = session_id

    def compose(self):
        # 左侧: MiniCode 图标和模型
        yield Static(
            "[bold green]MiniCode[/bold green]  [dim]{}[/dim]".format(self.model_name),
            markup=True,
        )

        # 中间: Session 信息
        yield Static(
            "[dim]Session: {}[/dim]".format(self.session_id),
            markup=True,
        )

        # 右侧: 快捷键提示
        yield Static(
            "[dim]Ctrl+P: 命令  |  Ctrl+L: 清屏[/dim]",
            markup=True,
        )


class ConnectionIndicator(Widget):
    """Shows connection status."""

    def __init__(self, connected: bool = True) -> None:
        super().__init__()
        self._connected = connected

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self.refresh()

    def render(self) -> str:
        if self._connected:
            return "[green]●[/green] Connected"
        return "[yellow]●[/yellow] Connecting..."