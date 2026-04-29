"""Permission management for bash commands and dangerous operations."""
import re
from typing import Optional


BASH_DANGEROUS_PATTERNS = [
    ("rm_rf_root", r"\brm\s+(-[rf]+)?\s*/\s*$", "Recursive delete of root"),
    ("sudo_shutdown", r"\bsudo\s+(shutdown|reboot|init\s+[06])", "System shutdown/reboot"),
    ("fork_bomb", r":\(\)\s*:\s*\|\s*:\s*&\s*;", "Fork bomb"),
    ("dd_zero", r"\bdd\s+.*of=/dev/", "Direct disk write"),
    ("mkfs", r"\bmkfs\b", "Filesystem format"),
    ("curl_pipe_sh", r"curl.*\|\s*(sh|bash|fish|zsh)", "Pipe to shell"),
    ("wget_pipe_sh", r"wget.*\|\s*(sh|bash|fish|zsh)", "Pipe to shell"),
    ("chmod_sensitive", r"chmod\s+[47]0[47]0", "Dangerous chmod"),
]


class BashSecurityValidator:
    """Validate bash commands for security risks.

    This is a more comprehensive validator than the simple one in graph.py.
    Used by the permission system for more thorough checks.
    """

    def __init__(self):
        self.patterns = BASH_DANGEROUS_PATTERNS
        self._compiled = [(n, re.compile(p), d) for n, p, d in self.patterns]

    def validate(self, command: str) -> list[tuple[str, str]]:
        """Validate a command and return list of violations."""
        violations = []
        for name, pattern, desc in self._compiled:
            if pattern.search(command):
                violations.append((name, desc))
        return violations

    def is_safe(self, command: str) -> tuple[bool, str]:
        """Check if command is safe to execute."""
        violations = self.validate(command)
        if violations:
            reasons = [v[1] for v in violations]
            return False, "; ".join(reasons)
        return True, ""

    def get_risk_level(self, command: str) -> str:
        """Get risk level: none, low, medium, high, critical."""
        violations = self.validate(command)
        if not violations:
            return "none"

        names = [v[0] for v in violations]
        critical = {"rm_rf_root", "fork_bomb", "dd_zero", "mkfs"}
        high = {"sudo_shutdown"}
        medium = {"curl_pipe_sh", "wget_pipe_sh"}

        if critical & set(names):
            return "critical"
        if high & set(names):
            return "high"
        if medium & set(names):
            return "medium"
        return "low"

    def describe_failures(self, command: str) -> str:
        """Get description of all failures."""
        violations = self.validate(command)
        if not violations:
            return "No issues detected"
        return "; ".join(v[1] for v in violations)


bash_validator = BashSecurityValidator()


_permission_mode = "allow"


def set_permission_mode(mode: str) -> None:
    """Set permission mode: 'allow', 'deny', 'prompt'."""
    global _permission_mode
    if mode in ("allow", "deny", "prompt"):
        _permission_mode = mode


def get_permission_mode() -> str:
    """Get current permission mode."""
    return _permission_mode


def check_permission(command: str, tool_name: str = "bash_tool") -> tuple[bool, str]:
    """Check if a command is allowed to run.

    Returns:
        tuple of (allowed, reason)
    """
    if tool_name != "bash_tool":
        return True, ""

    if _permission_mode == "deny":
        return False, "Permission mode is 'deny'"

    safe, reason = bash_validator.is_safe(command)
    if not safe:
        if _permission_mode == "prompt":
            return False, f"Requires confirmation: {reason}"
        return False, f"Blocked: {reason}"

    return True, ""


def get_permission_rules() -> list[dict]:
    """Get current permission rules summary."""
    return [
        {"mode": _permission_mode},
        {"risk_levels": ["none", "low", "medium", "high", "critical"]},
    ]
