"""Bash execution tools with YAML-based permission system."""
import subprocess
from pathlib import Path
from typing import Callable, Optional

from langchain_core.tools import tool

from minicode.tools.permission_config import (
    get_permission_config,
    PermissionConfig,
)


class BashSecurityValidator:
    """Validate bash commands for safety using PermissionConfig."""

    def __init__(self, config: Optional[PermissionConfig] = None):
        self.config = config or get_permission_config()

    def is_safe(self, command: str) -> tuple[bool, str]:
        """Check if command is safe to execute."""
        allowed, reason, risk, _ = self.config.check(command)
        if not allowed:
            return False, reason
        return True, ""


class BashTools:
    """Bash execution utilities with permission support."""

    def __init__(
        self,
        workdir: Optional[Path] = None,
        timeout: int = 120,
        permission_callback: Optional[Callable[[str], tuple[str, str]]] = None,
    ):
        self.workdir = workdir or Path.cwd()
        self.timeout = timeout
        self.validator = BashSecurityValidator()
        # Callback for interactive permission prompts (used in TUI)
        self.permission_callback = permission_callback

    def run(self, command: str, interactive: bool = True) -> str:
        """Run bash command with security check."""
        # Security validation
        safe, msg = self.validator.is_safe(command)
        if not safe:
            return f"[BLOCKED] {msg}"

        # Check if needs prompt for user confirmation
        if interactive and self.permission_callback:
            needs, extra = self.permission_callback(command)
            if needs == "prompt":
                return f"[PROMPT REQUIRED] {extra}"

        # Execute
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = (result.stdout + result.stderr).strip()
            return output[:50000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"[Error]: Timeout ({self.timeout}s)"
        except Exception as e:
            return f"[Error]: {e}"

    def set_permission_callback(self, callback: Callable[[str], tuple[str, str]]) -> None:
        """Set callback for interactive permission prompts."""
        self.permission_callback = callback


# Global instance
_bash_tools: Optional[BashTools] = None


def get_bash_tools(workdir: Optional[Path] = None, timeout: int = 120) -> BashTools:
    """Get or create global BashTools instance."""
    global _bash_tools
    if _bash_tools is None:
        _bash_tools = BashTools(workdir, timeout)
    return _bash_tools


def set_bash_tools(tools: BashTools) -> None:
    """Set global BashTools instance."""
    global _bash_tools
    _bash_tools = tools


def set_permission_callback(callback: Callable[[str], tuple[str, str]]) -> None:
    """Set permission callback for interactive prompts."""
    tools = get_bash_tools()
    tools.set_permission_callback(callback)


# Tool functions

@tool
def bash_tool(command: str) -> str:
    """Run a shell command.

    Args:
        command: Shell command to execute
    """
    tools = get_bash_tools()
    return tools.run(command)


def run_bash(command: str) -> str:
    """Run bash command (for internal use).

    Args:
        command: Shell command to execute
    """
    tools = get_bash_tools()
    return tools.run(command)


# Tool list for registration
BASH_TOOLS = [bash_tool]
