"""File operation tools: read, write, edit."""
import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


class FileTools:
    """File operation utilities."""

    def __init__(self, workdir: Optional[Path] = None):
        self.workdir = workdir or Path.cwd()

    def safe_path(self, path: str) -> Path:
        """Ensure path is within workdir."""
        resolved = (self.workdir / path).resolve()
        if not resolved.is_relative_to(self.workdir):
            raise ValueError(f"Path escapes workspace: {path}")
        return resolved

    def read(self, path: str, limit: Optional[int] = None) -> str:
        """Read file contents."""
        try:
            content = self.safe_path(path).read_text(encoding="utf-8")
            if limit and limit > 0:
                lines = content.splitlines()
                if len(lines) > limit:
                    content = "\n".join(lines[:limit])
                    content += f"\n... ({len(lines) - limit} more lines)"
            return content[:100000]  # Cap at 100KB
        except Exception as e:
            return f"[Error]: {e}"

    def write(self, path: str, content: str) -> str:
        """Write content to file."""
        try:
            fp = self.safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"[Error]: {e}"

    def edit(self, path: str, old_text: str, new_text: str) -> str:
        """Replace exact text in file."""
        try:
            fp = self.safe_path(path)
            content = fp.read_text(encoding="utf-8")
            if old_text not in content:
                return f"[Error]: Text not found in {path}"
            fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
            return f"Edited {path}"
        except Exception as e:
            return f"[Error]: {e}"


# Global instance
_file_tools: Optional[FileTools] = None


def get_file_tools(workdir: Optional[Path] = None) -> FileTools:
    """Get or create global FileTools instance."""
    global _file_tools
    if _file_tools is None:
        _file_tools = FileTools(workdir)
    return _file_tools


def set_file_tools(tools: FileTools) -> None:
    """Set global FileTools instance."""
    global _file_tools
    _file_tools = tools


# Tool functions

@tool
def read_file(path: str, limit: Optional[int] = None) -> str:
    """Read file contents.

    Args:
        path: File path relative to workdir
        limit: Optional line limit
    """
    tools = get_file_tools()
    return tools.read(path, limit)


@tool
def write_file(path: str, content: str) -> str:
    """Write content to file.

    Args:
        path: File path relative to workdir
        content: Content to write
    """
    tools = get_file_tools()
    return tools.write(path, content)


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace exact text in file.

    Args:
        path: File path relative to workdir
        old_text: Exact text to replace
        new_text: Replacement text
    """
    tools = get_file_tools()
    return tools.edit(path, old_text, new_text)


# Tool list for registration
FILE_TOOLS = [read_file, write_file, edit_file]
