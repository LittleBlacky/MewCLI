"""Dialog widgets for MiniCode TUI - Config and Permission dialogs."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    Label,
    Static,
)


class ConfigSaved(Message):
    """Message emitted when config is saved."""

    def __init__(self, config: dict) -> None:
        self.config = config
        super().__init__()


class PermissionResponse(Message):
    """Message emitted when permission is decided."""

    def __init__(self, command: str, action: str, pattern: str = "") -> None:
        self.command = command
        self.action = action  # "yes", "session_allow", "no", "deny"
        self.pattern = pattern
        super().__init__()


class ConfigDialog(Widget):
    """Interactive configuration dialog - 单界面设计"""

    CSS = """
    ConfigDialog {
        align: center middle;
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        border-radius: 8px;
        padding: 1 2;
    }

    ConfigDialog #title-bar {
        width: 100%;
        height: 1;
        background: $primary;
        color: $text;
        content-align: center middle;
    }

    ConfigDialog #close-hint {
        color: $text-muted;
    }

    ConfigDialog Button {
        margin: 1 0;
    }

    ConfigDialog Input {
        margin-bottom: 1;
    }

    ConfigDialog #save-btn {
        background: $success;
    }
    """

    # Configuration values
    provider = reactive("anthropic")
    model = reactive("claude-sonnet-4-7")
    api_key = reactive("")
    base_url = reactive("")

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+s", "save", "Save"),
    ]

    def __init__(self):
        super().__init__()
        self._closed = False
        self._result = None
        self._load_config()

    def _load_config(self) -> None:
        """Load current configuration."""
        from minicode.services.config import get_config_manager

        try:
            config = get_config_manager()
            model_cfg = config.get_model_config()
            self.provider = model_cfg.get("provider", "anthropic")
            self.model = model_cfg.get("model", "claude-sonnet-4-7")
            self.api_key = model_cfg.get("api_key") or ""
            self.base_url = model_cfg.get("base_url") or ""
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        """Create the dialog UI - 单一布局"""
        # Title bar
        with Horizontal(id="title-bar"):
            yield Static("[bold]Configuration[/bold]", id="title-text")
            yield Static("[dim]  |  Esc: Close  |  Ctrl+S: Save[/dim]", id="close-hint")

        # Provider (用户可输入)
        yield Label("[bold]Provider:[/bold]")
        yield Input(
            value=self.provider,
            id="provider-input",
            placeholder="anthropic, openai, ollama, deepseek, groq, gemini...",
        )

        # Model name
        yield Label("[bold]Model:[/bold]")
        yield Input(value=self.model, id="model-input", placeholder="e.g., claude-sonnet-4-7")

        # API Key
        yield Label("[bold]API Key:[/bold]")
        yield Input(
            value=self.api_key,
            id="api-key-input",
            placeholder="sk-xxxx (optional, uses env var if empty)",
            password=True,
        )

        # Base URL
        yield Label("[bold]Base URL:[/bold]")
        yield Input(
            value=self.base_url,
            id="base-url-input",
            placeholder="https://api.anthropic.com/v1 (optional)",
        )

        # Note
        yield Label("[yellow]Config auto-reloads on save.[/yellow]", id="note")

        # Action buttons
        with Horizontal(id="button-row"):
            yield Button("Cancel", id="cancel-btn", variant="error")
            yield Button("Save", id="save-btn", variant="success")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        input_map = {
            "provider-input": "provider",
            "model-input": "model",
            "api-key-input": "api_key",
            "base-url-input": "base_url",
        }
        field = input_map.get(event.control.id)
        if field:
            setattr(self, field, event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_close()
        elif event.button.id == "save-btn":
            self.action_save()

    def get_config(self) -> dict:
        """Get current configuration values."""
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
        }

    def action_close(self) -> None:
        """Close the dialog."""
        self._closed = True
        self.remove()

    def action_save(self) -> None:
        """Save configuration and close."""
        import os
        from minicode.services.config import get_config_manager

        try:
            config = get_config_manager()
            config.set("model.provider", self.provider)
            config.set("model.model", self.model)

            # API Key 和 Base URL 通过环境变量传递（create_chat_model 读取 env）
            if self.api_key:
                os.environ["MINICODE_API_KEY"] = self.api_key
            if self.base_url:
                os.environ["MINICODE_BASE_URL"] = self.base_url

            self._result = self.get_config()

            # 发送配置保存消息，触发热重载
            self.post_message(ConfigSaved(self._result))
        except Exception as e:
            self._result = {"error": str(e)}

        self.action_close()

    @property
    def is_closed(self) -> bool:
        """Check if dialog is closed."""
        return self._closed

    @property
    def result(self) -> dict:
        """Get saved configuration result."""
        return self._result


class PermissionPromptDialog(Widget):
    """Interactive permission prompt dialog - 选项 a/y/n/d 设计"""

    CSS = """
    PermissionPromptDialog {
        align: center middle;
        width: 70;
        height: auto;
        background: $surface;
        border: thick $warning;
        border-radius: 8px;
        padding: 1 2;
    }

    PermissionPromptDialog #title-bar {
        width: 100%;
        height: 1;
        background: $warning;
        color: $text;
        content-align: center middle;
    }

    PermissionPromptDialog #command-display {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        background: $surface-darken-1;
        border: solid $primary;
        padding: 0 1;
    }

    PermissionPromptDialog #command-text {
        color: $text;
    }

    PermissionPromptDialog #info-row {
        width: 100%;
        height: 1;
        color: $text-muted;
    }

    PermissionPromptDialog #risk-badge {
        color: $warning;
    }

    PermissionPromptDialog Button {
        margin: 1 1;
    }

    PermissionPromptDialog #option-hint {
        width: 100%;
        color: $text-muted;
        padding-top: 1;
    }

    PermissionPromptDialog #btn-yes {
        background: $success;
    }

    PermissionPromptDialog #btn-session {
        background: $primary;
    }

    PermissionPromptDialog #btn-no {
        background: $surface-darken-1;
    }

    PermissionPromptDialog #btn-deny {
        background: $error;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("y", "allow_once", "Allow Once"),
        ("a", "allow_session", "Allow Type"),
        ("n", "deny_once", "Deny Once"),
        ("d", "deny_always", "Deny Always"),
    ]

    def __init__(self, command: str, reason: str = "", risk: str = "medium", pattern: str = ""):
        super().__init__()
        self.command = command
        self.reason = reason
        self.risk = risk
        self.pattern = pattern
        self._closed = False
        self._action = None

    def compose(self) -> ComposeResult:
        """Create the dialog UI."""
        # Title bar
        with Horizontal(id="title-bar"):
            yield Static("[bold]⚠ Permission Required[/bold]", id="title-text")

        # Command display
        with VerticalScroll(id="command-display"):
            yield Static(f"Command: {self.command}", id="command-text")

        # Info row
        with Horizontal(id="info-row"):
            risk_color = self._get_risk_color()
            yield Static(f"{risk_color}[{self.risk}][/{risk_color}]", id="risk-badge")
            yield Static(f"  |  {self.reason or 'Unknown command'}", id="reason-text")

        # Options hint
        yield Static(
            "[dim]Options:[/dim] "
            "[green][Y] Allow once[/green]  "
            "[cyan][A] Allow type ({})[/cyan]  "
            "[yellow][N] Deny once[/yellow]  "
            "[red][D] Add to deny[/red]",
            id="option-hint",
        )

        # Action buttons
        with Horizontal(id="button-row"):
            yield Button("Allow (y)", id="btn-yes", variant="success")
            yield Button("Allow Type (a)", id="btn-session", variant="primary")
            yield Button("Deny (n)", id="btn-no", variant="default")
            yield Button("Deny+ (d)", id="btn-deny", variant="error")

    def _get_risk_color(self) -> str:
        """Get color for risk level."""
        colors = {
            "critical": "[red]",
            "high": "[orange]",
            "medium": "[yellow]",
            "low": "[green]",
            "none": "[dim]",
        }
        return colors.get(self.risk, "[yellow]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_actions = {
            "btn-yes": "yes",
            "btn-session": "session_allow",
            "btn-no": "no",
            "btn-deny": "deny",
        }
        action = button_actions.get(event.button.id)
        if action:
            self._action = action
            self.post_message(PermissionResponse(self.command, action, self.pattern))
            self.action_close()

    def action_close(self) -> None:
        """Close the dialog without action."""
        self._closed = True
        self.remove()

    def action_allow_once(self) -> None:
        """Allow command once."""
        self._action = "yes"
        self.post_message(PermissionResponse(self.command, "yes", self.pattern))
        self.action_close()

    def action_allow_session(self) -> None:
        """Allow command type (session pattern)."""
        self._action = "session_allow"
        self.post_message(PermissionResponse(self.command, "session_allow", self.pattern))
        self.action_close()

    def action_deny_once(self) -> None:
        """Deny command once."""
        self._action = "no"
        self.post_message(PermissionResponse(self.command, "no", self.pattern))
        self.action_close()

    def action_deny_always(self) -> None:
        """Deny command always (add to deny list)."""
        self._action = "deny"
        self.post_message(PermissionResponse(self.command, "deny", self.pattern))
        self.action_close()

    @property
    def is_closed(self) -> bool:
        """Check if dialog is closed."""
        return self._closed

    @property
    def action(self) -> Optional[str]:
        """Get the action that was taken."""
        return self._action