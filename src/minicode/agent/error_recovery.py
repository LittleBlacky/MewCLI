"""Error recovery module - Handles agent errors gracefully."""
import time
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum


class ErrorType(Enum):
    """Types of errors the agent can encounter."""
    MAX_TOKENS = "max_tokens"
    PROMPT_TOO_LONG = "prompt_too_long"
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


@dataclass
class RecoveryResult:
    """Result of error recovery attempt."""
    success: bool
    strategy: str
    message: str
    retry_count: int = 0


class ErrorRecovery:
    """Handles error recovery with multiple strategies.

    Recovery strategies:
    1. max_tokens -> inject continuation, retry
    2. prompt_too_long -> compact history, retry
    3. rate_limit -> exponential backoff, retry
    4. connection -> wait and retry
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_counts: dict[ErrorType, int] = {}

    def identify_error(self, error: Exception) -> ErrorType:
        """Identify the type of error."""
        error_str = str(error).lower()

        if "max_tokens" in error_str or "maximum context" in error_str:
            return ErrorType.MAX_TOKENS
        elif "too long" in error_str or "token limit" in error_str:
            return ErrorType.PROMPT_TOO_LONG
        elif "rate limit" in error_str or "429" in error_str:
            return ErrorType.RATE_LIMIT
        elif "connection" in error_str or "timeout" in error_str:
            return ErrorType.CONNECTION
        else:
            return ErrorType.UNKNOWN

    def get_backoff_seconds(self, error_type: ErrorType, retry_count: int) -> float:
        """Get exponential backoff seconds."""
        base_times = {
            ErrorType.RATE_LIMIT: 2.0,
            ErrorType.CONNECTION: 1.0,
            ErrorType.MAX_TOKENS: 0.5,
            ErrorType.PROMPT_TOO_LONG: 0.0,
            ErrorType.UNKNOWN: 1.0,
        }
        base = base_times.get(error_type, 1.0)
        return min(base * (2 ** retry_count), 60.0)  # Max 60 seconds

    def recover(
        self,
        error: Exception,
        callback: Optional[Callable] = None,
    ) -> RecoveryResult:
        """Attempt to recover from error."""
        error_type = self.identify_error(error)
        retry_count = self.retry_counts.get(error_type, 0)

        if retry_count >= self.max_retries:
            return RecoveryResult(
                success=False,
                strategy="max_retries_exceeded",
                message=f"Failed after {self.max_retries} retries: {error}",
                retry_count=retry_count,
            )

        # Apply backoff
        backoff = self.get_backoff_seconds(error_type, retry_count)
        if backoff > 0:
            time.sleep(backoff)

        # Increment retry count
        self.retry_counts[error_type] = retry_count + 1

        # Strategy based on error type
        strategies = {
            ErrorType.MAX_TOKENS: "continue_with_compact",
            ErrorType.PROMPT_TOO_LONG: "compact_and_retry",
            ErrorType.RATE_LIMIT: "backoff_and_retry",
            ErrorType.CONNECTION: "wait_and_retry",
            ErrorType.UNKNOWN: "retry",
        }

        return RecoveryResult(
            success=True,
            strategy=strategies.get(error_type, "retry"),
            message=f"Recovered from {error_type.value}, attempt {retry_count + 1}",
            retry_count=retry_count + 1,
        )

    def reset(self, error_type: Optional[ErrorType] = None) -> None:
        """Reset retry counters."""
        if error_type:
            self.retry_counts[error_type] = 0
        else:
            self.retry_counts.clear()

    def should_compact(self, error: Exception) -> bool:
        """Check if error requires context compaction."""
        error_type = self.identify_error(error)
        return error_type in (ErrorType.MAX_TOKENS, ErrorType.PROMPT_TOO_LONG)


class RecoveryManager:
    """Manages error recovery for the agent."""

    def __init__(self):
        self.recovery = ErrorRecovery()
        self.compact_callback: Optional[Callable] = None

    def set_compact_callback(self, callback: Callable) -> None:
        """Set callback for context compaction."""
        self.compact_callback = callback

    def handle_error(self, error: Exception) -> RecoveryResult:
        """Handle error and attempt recovery."""
        result = self.recovery.recover(error)

        if result.success and self.compact_callback:
            if self.recovery.should_compact(error):
                try:
                    self.compact_callback()
                    result.message += " (context compacted)"
                except Exception as e:
                    result.message += f" (compact failed: {e})"

        return result


__all__ = ["ErrorRecovery", "RecoveryManager", "ErrorType", "RecoveryResult"]
