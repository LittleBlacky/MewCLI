"""Permission hook for PreToolUse event using YAML config."""
from typing import Optional

from minicode.tools.hook_tools import get_hook_manager
from minicode.tools.permission_config import (
    get_permission_config,
    reset_permission_config,
    PermissionConfig,
    BUILTIN_DANGEROUS_PATTERNS,
)


class PermissionCheckResult:
    """Result of permission check."""

    def __init__(
        self,
        allowed: bool,
        reason: str = "",
        risk: str = "none",
        matched: list[str] | None = None,
        needs_user_input: bool = False,
        command: str = "",
        pattern: str = "",
    ):
        self.allowed = allowed
        self.reason = reason
        self.risk = risk
        self.matched = matched or []
        self.needs_user_input = needs_user_input
        self.command = command
        self.pattern = pattern

    def to_dict(self) -> dict:
        return {
            "blocked": not self.allowed,
            "block_reason": self.reason,
            "messages": [f"Risk level: {self.risk}"] if self.risk != "none" else [],
            "updated_input": None,
            "needs_user_input": self.needs_user_input,
        }


def create_permission_checker(config_path: Optional[str] = None) -> callable:
    """Create a permission check function with the given config.

    Args:
        config_path: Optional path to permissions.yaml

    Returns:
        A hook function that checks command permissions
    """

    def check_command_permission(context: dict) -> dict:
        """Permission check hook for PreToolUse.

        Checks command against:
        1. Built-in dangerous patterns (cannot be overridden)
        2. User deny patterns (from permissions.yaml)
        3. User allow patterns (from permissions.yaml)
        4. Session patterns
        """
        # Handle both dict and string input for flexibility
        if isinstance(context, str):
            # If called with a command string directly
            command = context
            context = {}
        else:
            tool_input = context.get("tool_input", {})
            command = tool_input.get("command", "")

        if not command:
            return {"blocked": False, "block_reason": "", "messages": [], "updated_input": None}

        # Load config (lazy loading)
        config = get_permission_config()
        if config_path:
            config = PermissionConfig(config_path)

        allowed, reason, risk_level, matched = config.check(command)

        # Always block dangerous built-in patterns
        if not allowed:
            return {
                "blocked": True,
                "block_reason": reason,
                "messages": [f"Risk level: {risk_level}"],
                "updated_input": None,
            }

        # Check if needs prompt
        needs_prompt = config.needs_prompt(command)
        if needs_prompt:
            pattern = config.extract_command_type(command)
            return {
                "blocked": False,  # Don't block, just flag for prompt
                "block_reason": "",
                "messages": [],
                "updated_input": None,
                "needs_user_input": True,
                "command": command,
                "pattern": pattern,
                "reason": reason,
                "risk": risk_level,
            }

        return {"blocked": False, "block_reason": "", "messages": [], "updated_input": None}

    return check_command_permission


def register_permission_hooks(config_path: Optional[str] = None) -> None:
    """Register permission check hooks with HookManager.

    Args:
        config_path: Optional path to permissions.yaml
    """
    manager = get_hook_manager()
    checker = create_permission_checker(config_path)
    manager.register_python_hook("PreToolUse", checker, matcher="bash_tool")


# Default check function using global config
_default_checker = create_permission_checker()


def check_command_permission(context: dict) -> dict:
    """Default permission check hook for PreToolUse.

    Uses the global PermissionConfig loaded from .minicode/permissions.yaml

    Args:
        context: The hook context dict with 'tool_input' containing 'command'

    Returns:
        dict with 'blocked', 'block_reason', 'messages', 'updated_input'
    """
    return create_permission_checker()(context)


def check_command(command: str) -> PermissionCheckResult:
    """Check command permission without hook context.

    Args:
        command: The command to check

    Returns:
        PermissionCheckResult with detailed information
    """
    config = get_permission_config()
    allowed, reason, risk, matched = config.check(command)

    if not allowed:
        return PermissionCheckResult(
            allowed=False,
            reason=reason,
            risk=risk,
            matched=matched,
            command=command,
        )

    # Check if needs prompt
    needs_prompt = config.needs_prompt(command)
    pattern = config.extract_command_type(command)

    if needs_prompt:
        return PermissionCheckResult(
            allowed=True,
            reason=reason,
            risk=risk,
            needs_user_input=True,
            command=command,
            pattern=pattern,
        )

    return PermissionCheckResult(
        allowed=True,
        reason=reason,
        risk=risk,
        matched=matched,
        command=command,
    )


def register_permission_hooks_default() -> None:
    """Register permission check hooks with default config."""
    manager = get_hook_manager()
    manager.register_python_hook("PreToolUse", check_command_permission, matcher="bash_tool")


# Alias for compatibility
PermissionHook = type(
    "PermissionHook",
    (),
    {
        "check": lambda self, cmd: check_command(cmd).to_dict(),
    },
)()


def get_permission_rules() -> dict:
    """Get current permission rules summary."""
    config = get_permission_config()
    return {
        "config": config.get_config_summary(),
        "builtin_patterns": config.get_builtin_patterns(),
    }


def reload_permission_config() -> None:
    """Reload permission configuration from file."""
    reset_permission_config()