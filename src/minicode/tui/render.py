"""Rich text rendering utilities for MiniCode TUI."""
from __future__ import annotations

import re
from typing import Optional
from pathlib import Path

from rich.console import Console, ConsoleOptions, RenderResult
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED


# 创建专用控制台（用于渲染到字符串）
_console = Console(force_terminal=False)


def extract_code_blocks(content: str) -> list[tuple[str, str, str]]:
    """提取代码块

    Returns:
        list of (language, code, full_block)
    """
    pattern = r'```(\w*)\n?(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def highlight_code(code: str, language: str = "python") -> Syntax:
    """生成语法高亮的代码块"""
    theme_map = {
        "python": "monokai",
        "bash": "dracula",
        "shell": "dracula",
        "sh": "dracula",
        "javascript": "monokai",
        "js": "monokai",
        "typescript": "monokai",
        "ts": "monokai",
        "json": "github-dark",
        "yaml": "dracula",
        "yml": "dracula",
        "rust": "github-dark",
        "go": "dracula",
        "java": "dracula",
        "c": "dracula",
        "cpp": "dracula",
        "sql": "dracula",
    }

    theme = theme_map.get(language.lower(), "monokai")

    return Syntax(
        code.strip(),
        language if language else "text",
        theme=theme,
        line_numbers=False,
        word_wrap=True,
    )


def render_markdown(content: str) -> Markdown:
    """渲染 Markdown 内容"""
    return Markdown(
        content,
        code_theme="monokai",
        hyperlinks=True,
    )


def render_message(
    content: str,
    sender: str = "user",
    show_sender: bool = True,
) -> Panel:
    """渲染消息气泡

    Args:
        content: 消息内容
        sender: "user" 或 "agent"
        show_sender: 是否显示发送者标签

    Returns:
        Panel with styled message
    """
    # 确定样式
    if sender == "user":
        border_style = "cyan"
        title = "[cyan]You[/cyan]" if show_sender else None
    else:
        border_style = "green"
        title = "[green]MiniCode[/green]" if show_sender else None

    # 渲染内容
    rendered = render_content(content)

    return Panel(
        rendered,
        border_style=border_style,
        title=title,
        box=ROUNDED,
        padding=(1, 2),
    )


def render_content(content: str) -> Text:
    """渲染消息内容（支持 Markdown 和代码高亮）"""
    from rich.console import Group
    from io import StringIO

    # 如果包含代码块，特殊处理
    if "```" in content:
        parts = []
        lines = content.split("\n")
        in_code = False
        code_lines = []
        code_lang = ""

        for line in lines:
            if line.startswith("```"):
                if not in_code:
                    in_code = True
                    code_lang = line[3:].strip()
                else:
                    # 代码块结束
                    code = "\n".join(code_lines)
                    parts.append(highlight_code(code, code_lang))
                    in_code = False
                    code_lines = []
                    code_lang = ""
            elif in_code:
                code_lines.append(line)
            else:
                # 普通文本，尝试渲染为 Markdown
                if line.strip():
                    parts.append(render_markdown(line))

        if in_code and code_lines:
            code = "\n".join(code_lines)
            parts.append(highlight_code(code, code_lang))

        if len(parts) == 1:
            if isinstance(parts[0], Markdown):
                return parts[0]
            return Text(parts[0])

        return Group(*parts) if parts else Text(content)
    else:
        # 纯文本
        return Text(content)


def render_tool_call(tool_name: str, args: dict, result: str = "") -> Panel:
    """渲染工具调用"""
    from rich.pretty import Pretty

    content = f"[bold cyan]{tool_name}[/bold cyan]\n"
    if args:
        content += f"[dim]{Pretty(args)}[/dim]\n"
    if result:
        content += f"\n{result}"

    return Panel(
        Text.from_markup(content),
        border_style="yellow",
        title="[yellow]Tool[/yellow]",
        box=ROUNDED,
    )


def render_error(error: str) -> Panel:
    """渲染错误信息"""
    return Panel(
        Text.from_markup(f"[red]{error}[/red]"),
        border_style="red",
        title="[red]Error[/red]",
        box=ROUNDED,
    )


def render_file_preview(path: str, max_lines: int = 50) -> Optional[Panel]:
    """渲染文件预览"""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")[:max_lines]

        if len(content.split("\n")) > max_lines:
            lines.append(f"... (+{len(content.split(chr(10))) - max_lines} more lines)")

        code = "\n".join(lines)
        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)

        return Panel(
            syntax,
            border_style="blue",
            title=f"[blue]@{path}[/blue]",
            box=ROUNDED,
        )
    except Exception:
        return None


def to_ansi(text: str) -> str:
    """将 Rich 渲染结果转为 ANSI 转义序列"""
    from io import StringIO
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor")

    if "```" in text:
        # 渲染为 Markdown
        console.print(render_markdown(text))
    else:
        console.print(Text(text))

    return buf.getvalue()


# 导出所有组件
__all__ = [
    "extract_code_blocks",
    "highlight_code",
    "render_markdown",
    "render_message",
    "render_content",
    "render_tool_call",
    "render_error",
    "render_file_preview",
    "to_ansi",
]
