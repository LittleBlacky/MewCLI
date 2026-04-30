"""MiniCode TUI widgets."""
from minicode.tui.components import StatusBar, CommandPalette, ToolCallLog, MessageBubble

# New widgets
from .header import TUIHeader
from .message import MessageList
from .input import InputArea
from .status import TUIStatusBar

__all__ = [
    # Existing
    "StatusBar",
    "CommandPalette",
    "ToolCallLog",
    "MessageBubble",
    # New
    "TUIHeader",
    "MessageList",
    "InputArea",
    "TUIStatusBar",
]