"""Permission hook for PreToolUse event using YAML config."""
from typing import Optional

from minicode.tools.hook_tools import get_hook_manager
from minicode.tools.permission_config import (
    get_permission_config,
    reset_permission_config,
    PermissionConfig,
)


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
            return {
                "blocked": False,
                "block_reason": "",
                "messages": [],
                "updated_input": None,
            }

        # Load config (lazy loading)
        config = get_permission_config()
        if config_path:
            config = PermissionConfig(config_path)

        allowed, reason, risk_level, matched = config.check(command)

        if allowed:
            return {
                "blocked": False,
                "block_reason": "",
                "messages": [],
                "updated_input": None,
            }
        else:
            return {
                "blocked": True,
                "block_reason": reason,
                "messages": [f"Risk level: {risk_level}"],
                "updated_input": None,
            }

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
    # Handle both dict and string input for flexibility
    if isinstance(context, str):
        # If called with a command string directly
        command = context
        context = {}
    else:
        tool_input = context.get("tool_input", {})
        command = tool_input.get("command", "")

    if not command:
        return {
            "blocked": False,
            "block_reason": "",
            "messages": [],
            "updated_input": None,
        }

    config = get_permission_config()
    allowed, reason, risk_level, matched = config.check(command)

    if allowed:
        return {
            "blocked": False,
            "block_reason": "",
            "messages": [],
            "updated_input": None,
        }
    else:
        return {
            "blocked": True,
            "block_reason": reason,
            "messages": [f"Risk level: {risk_level}"],
            "updated_input": None,
        }


def register_permission_hooks_default() -> None:
    """Register permission check hooks with default config."""
    manager = get_hook_manager()
    manager.register_python_hook("PreToolUse", check_command_permission, matcher="bash_tool")


# Alias for compatibility
PermissionHook = type("PermissionHook", (), {
    "check": lambda self, cmd: (False, "Use permission_config.check() instead"),
})()


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