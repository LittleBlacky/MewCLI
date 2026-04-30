"""Header widget for MiniCode TUI."""
from textual.widgets import Header
from textual.widget import Widget
from textual.css.query import NoMatches


class TUIHeader(Header):
    """Custom header with MiniCode branding."""

    def compose(self):
        yield super().compose()
