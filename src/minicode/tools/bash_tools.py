"""Bash execution tools with YAML-based permission system.

Claude Code-style terminal interaction:
- 当需要权限确认时，同步等待用户输入 y/a/n/d
- 使用 built-in dangerous patterns 阻止危险命令
- 支持 session patterns (选项 a) 一次性允许同类命令
- 支持 REPL 模式下的交互式对话框
"""
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Callable, Awaitable

from langchain_core.tools import tool

from minicode.tools.permission_config import (
    get_permission_config,
    PermissionConfig,
)

# Global permission callback for REPL integration
_permission_callback: Optional[Callable[[str], tuple[str, str]]] = None


def set_global_permission_callback(callback: Optional[Callable[[str], tuple[str, str]]]) -> None:
    """Set global permission callback for REPL mode."""
    global _permission_callback
    _permission_callback = callback


def get_global_permission_callback() -> Optional[Callable[[str], tuple[str, str]]]:
    """Get global permission callback."""
    return _permission_callback


class BashSecurityValidator:
    """Validate bash commands for safety using PermissionConfig."""

    def __init__(self, config: Optional[PermissionConfig] = None):
        self._config = config  # Optional override

    @property
    def config(self) -> PermissionConfig:
        """Get config - always uses global current config."""
        if self._config is None:
            return get_permission_config()
        return self._config

    def is_safe(self, command: str) -> tuple[bool, str]:
        """Check if command is safe to execute."""
        cfg = self.config  # Always get fresh global config
        allowed, reason, risk, _ = cfg.check(command)
        if not allowed:
            return False, reason
        return True, ""


class BashTools:
    """Bash execution utilities with terminal-style permission prompts.

    Claude Code-style interaction:
    - 同步等待用户输入 y/a/n/d
    - 支持选项 a 允许同类命令
    - 支持 REPL 模式下的交互式对话框
    """

    def __init__(
        self,
        workdir: Optional[Path] = None,
        timeout: int = 120,
        permission_callback: Optional[Callable[[str], Awaitable[tuple[str, str]]]] = None,
    ):
        self.workdir = workdir or Path.cwd()
        self.timeout = timeout
        self.validator = BashSecurityValidator()
        # Session patterns cache (选项 a)
        self._session_patterns: set[str] = set()
        # Permission callback (for REPL mode)
        self._permission_callback = permission_callback

    def set_permission_callback(self, callback: Callable[[str], Awaitable[tuple[str, str]]]) -> None:
        """Set async permission callback for REPL mode."""
        self._permission_callback = callback

    def _ask_permission(self, command: str) -> tuple[str, str]:
        """Ask user for permission in terminal - 同步阻塞等待.

        Returns:
            tuple of (action, pattern)
            - ("allow", pattern) - 允许这一次
            - ("session_allow", pattern) - 允许同类命令
            - ("deny", "") - 拒绝这一次
            - ("deny_always", "") - 加入 deny 列表（暂不支持）
        """
        config = get_permission_config()
        allowed, reason, risk, matched = config.check(command)
        pattern = config.extract_command_type(command)

        # 已禁止的命令
        if not allowed:
            return ("block", reason)

        # 检查 session patterns
        for sp in self._session_patterns:
            compiled = config._glob_to_regex(sp)
            if compiled.search(command):
                return ("session_ok", pattern)

        # 检查是否需要 prompt
        if not config.needs_prompt(command):
            return ("allow", "")

        # REPL 模式下使用全局回调
        if _permission_callback := get_global_permission_callback():
            return _permission_callback(command)

        # 同步等待输入
        return self._prompt_user(command, reason, risk, pattern)

    async def _ask_permission_async(self, command: str) -> tuple[str, str]:
        """Ask user for permission async - for REPL mode.

        Returns:
            tuple of (action, pattern)
            - ("allow", pattern) - 允许这一次
            - ("session_allow", pattern) - 允许同类命令
            - ("session_ok", pattern) - session pattern match
            - ("deny", "") - 拒绝这一次
        """
        config = get_permission_config()
        allowed, reason, risk, matched = config.check(command)
        pattern = config.extract_command_type(command)

        # 已禁止的命令
        if not allowed:
            return ("block", reason)

        # 检查 session patterns (both local and global)
        for sp in self._session_patterns:
            compiled = config._glob_to_regex(sp)
            match = config._match_startswith(compiled, "glob", command)
            if match:
                return ("session_ok", pattern)

        # Also check global config session patterns
        global_patterns = config.get_session_patterns()
        for sp in global_patterns:
            compiled = config._glob_to_regex(sp)
            match = config._match_startswith(compiled, "glob", command)
            if match:
                return ("session_ok", pattern)

        # 检查是否需要 prompt
        needs_prompt = config.needs_prompt(command)
        if not needs_prompt:
            return ("allow", "")

        # REPL 模式下使用全局回调 (同步)
        if cb := get_global_permission_callback():
            return cb(command)

        # 异步回调
        if self._permission_callback:
            try:
                action = await self._permission_callback(command)
                if action == "allow":
                    return ("allow", "")
                elif action == "session":
                    self._session_patterns.add(pattern)
                    config.add_session_pattern(command)
                    return ("session_allow", pattern)
                elif action in ("deny", "permanent", "cancel"):
                    return ("deny", "")
            except Exception:
                return ("deny", "")

        # 回退到同步模式
        return self._prompt_user(command, reason, risk, pattern)

    def _prompt_user(self, command: str, reason: str, risk: str, pattern: str) -> tuple[str, str]:
        """Prompt user for permission - 同步阻塞."""
        # 颜色定义
        colors = {
            "critical": "\033[91m",  # 红色
            "high": "\033[93m",      # 橙色
            "medium": "\033[93m",    # 黄色
            "low": "\033[92m",       # 绿色
            "none": "\033[90m",      # 灰色
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
        print(f"  [d]  Add to deny list (permanent)")
        print()

        while True:
            try:
                choice = input("Your choice (y/a/n/d): ").strip().lower()
                if choice in ("y", "yes"):
                    return ("allow", pattern)
                elif choice in ("a", "allow-type"):
                    # 添加到 session patterns
                    self._session_patterns.add(pattern)
                    config = get_permission_config()
                    config.add_session_pattern(command)
                    return ("session_allow", pattern)
                elif choice in ("n", "no", ""):
                    return ("deny", "")
                elif choice == "d":
                    print("  (Deny list editing via .minicode/permissions.yaml)")
                    return ("deny", "")
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.")
                return ("deny", "")

    def run(self, command: str) -> str:
        """Run bash command with security check and permission prompts."""
        # Security validation (built-in dangerous patterns)
        safe, msg = self.validator.is_safe(command)
        if not safe:
            return f"[BLOCKED] {msg}"

        # Ask for permission (同步阻塞)
        action, extra = self._ask_permission(command)

        if action == "block":
            return f"[BLOCKED] {extra}"

        if action == "deny":
            return f"[DENIED] Command rejected by user"

        # Execute command
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

    async def run_async(self, command: str) -> str:
        """Run bash command with async permission prompt (for REPL mode)."""
        # Security validation (built-in dangerous patterns)
        safe, msg = self.validator.is_safe(command)
        if not safe:
            return f"[BLOCKED] {msg}"

        # Ask for permission (async)
        action, extra = await self._ask_permission_async(command)

        if action == "block":
            return f"[BLOCKED] {extra}"

        if action == "deny":
            return f"[DENIED] Command rejected by user"

        # Execute command (still sync subprocess for shell commands)
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

    def clear_session_patterns(self) -> None:
        """Clear session patterns."""
        self._session_patterns.clear()
        config = get_permission_config()
        config.clear_session_patterns()


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


# Tool functions

@tool
def bash_tool(command: str) -> str:
    """Run a shell command.

    Args:
        command: Shell command to execute
    """
    tools = get_bash_tools()
    return tools.run(command)


@tool
async def bash_tool_async(command: str) -> str:
    """Run a shell command with async permission prompt (for REPL mode).

    Args:
        command: Shell command to execute
    """
    tools = get_bash_tools()
    return await tools.run_async(command)


# Tool list for registration
BASH_TOOLS = [bash_tool, bash_tool_async]


def run_bash(command: str) -> str:
    """Run bash command (for internal use).

    Args:
        command: Shell command to execute
    """
    tools = get_bash_tools()
    return tools.run(command)
