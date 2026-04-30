"""Session Manager - 分层防御的上下文管理"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from minicode.tools.memory_tools import MemoryManager
from minicode.tools.compact_tools import compact_messages


WORKDIR = Path.cwd()
STORAGE_DIR = WORKDIR / ".minicode"
OUTPUT_DIR = STORAGE_DIR / "outputs"

# 上下文限制配置
DEFAULT_CONTEXT_LIMIT = 50000  # 字符数限制（用于粗略估计）
LLM_MAX_TOKENS = 150000       # Claude 200K，预留 50K buffer
MAX_OUTPUT_CHARS = 15000     # 单条消息超过此长度需要保护
COMPACT_THRESHOLD_RATIO = 0.7  # 超过 70% 容量就开始压缩


@dataclass
class SessionConfig:
    """会话配置"""
    compact_threshold: int = 50      # 消息数量阈值
    compact_keep_recent: int = 5     # 压缩时保留最近N条
    memory_on_task_complete: bool = True
    reflect_on_idle: bool = True
    reflect_interval: int = 10
    context_limit: int = DEFAULT_CONTEXT_LIMIT
    max_output_chars: int = MAX_OUTPUT_CHARS
    compact_ratio: float = COMPACT_THRESHOLD_RATIO


@dataclass
class SessionMetrics:
    """会话指标"""
    total_turns: int = 0
    total_tools_called: int = 0
    tasks_completed: int = 0
    last_compact_turn: int = 0
    last_reflect_turn: int = 0
    session_start: float = field(default_factory=time.time)
    compact_count: int = 0
    output_saved_count: int = 0


class ContextOverflowError(Exception):
    """上下文超限异常"""
    def __init__(self, message: str = "Context overflow"):
        super().__init__(message)


class SessionManager:
    """会话管理器 - 分层防御的上下文管理"""

    def __init__(self, config: Optional[SessionConfig] = None):
        self.config = config or SessionConfig()
        self.metrics = SessionMetrics()
        self.memory_manager = MemoryManager()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.task_history: list[dict] = []
        self.completed_tasks: list[dict] = []

    # ========== Layer 1: 输入保护 (Preflight Check) ==========

    def estimate_tokens(self, messages: list) -> int:
        """估算消息列表的 token 数量

        简化估算：中文约2字符=1token，英文约4字符=1token
        """
        total = 0
        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                text = str(msg.content)
                # 简单估算
                total += len(text) // 2
        return total

    def estimate_output_tokens(self, messages: list) -> int:
        """估算可能的最大输出（预留空间）"""
        current = self.estimate_tokens(messages)
        # 预留 10K tokens 给输出
        return current + 10000

    def should_precompact(self, messages: list) -> bool:
        """检查是否应该预压缩"""
        estimated = self.estimate_output_tokens(messages)
        limit = LLM_MAX_TOKENS * self.config.compact_ratio
        return estimated > limit

    def preflight_check(self, messages: list) -> list:
        """运行前检查 - 确保输入安全

        返回可以安全发送给 LLM 的消息列表
        """
        if not messages:
            return messages

        # 检查是否需要预压缩
        if self.should_precompact(messages):
            messages = self.compact(messages, aggressive=False)

        # 再次检查
        estimated = self.estimate_tokens(messages)
        limit = LLM_MAX_TOKENS * 0.85  # 85% 限制

        if estimated > limit:
            messages = self.compact(messages, aggressive=True)

        return messages

    # ========== Layer 2: 输出保护 (Output Protection) ==========

    def protect_output(self, messages: list) -> list:
        """保护过长的输出消息

        将过长的消息内容保存到文件，上下文只保留摘要
        """
        protected_messages = []

        for msg in messages:
            # 检查是否是 AI 消息且内容过长
            if (hasattr(msg, "content") and msg.content and
                isinstance(msg, AIMessage) and
                len(msg.content) > self.config.max_output_chars):

                saved_path = self._save_long_output(msg.content)
                summary = self._summarize_content(msg.content)

                # 创建保护后的消息
                protected_msg = AIMessage(
                    content=f"{summary}\n\n[详细内容已保存到: {saved_path}]"
                )
                protected_messages.append(protected_msg)
                self.metrics.output_saved_count += 1
            else:
                protected_messages.append(msg)

        return protected_messages

    def _save_long_output(self, content: str) -> str:
        """保存长输出到文件"""
        timestamp = int(time.time() * 1000)
        filename = f"output_{timestamp}.txt"
        filepath = OUTPUT_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath.relative_to(WORKDIR))

    def _summarize_content(self, content: str, max_chars: int = 300) -> str:
        """生成内容摘要（简化版本）"""
        # 简单截取前 N 个字符
        if len(content) <= max_chars:
            return content

        lines = content.split('\n')
        summary_lines = []
        char_count = 0

        for line in lines:
            if char_count + len(line) > max_chars:
                break
            summary_lines.append(line)
            char_count += len(line)

        result = '\n'.join(summary_lines)
        if len(content) > len(result):
            result += f"\n\n... (共 {len(content)} 字符)"
        return result

    # ========== Layer 3: 周期性压缩 (Periodic Compact) ==========

    def check_should_compact(self, messages: list) -> bool:
        """检查是否需要压缩"""
        turn_number = self.metrics.total_turns
        since_last = turn_number - self.metrics.last_compact_turn

        if len(messages) >= self.config.compact_threshold:
            return True

        if since_last >= 12:
            return True

        return False

    def compact(self, messages: list, aggressive: bool = False) -> list:
        """执行上下文压缩"""
        keep = 3 if aggressive else self.config.compact_keep_recent
        compacted = compact_messages(messages, keep_recent=keep)

        self.metrics.last_compact_turn = self.metrics.total_turns
        self.metrics.compact_count += 1

        return compacted

    # ========== Layer 4: 错误恢复 (Error Recovery) ==========

    def handle_overflow(self, error: Exception, messages: list) -> tuple[list, bool]:
        """处理上下文溢出错误

        Args:
            error: 异常对象
            messages: 当前消息列表

        Returns:
            (processed_messages, should_retry)
        """
        error_str = str(error).lower()

        # 判断是否是上下文相关错误
        is_overflow = (
            "context" in error_str or
            "token" in error_str or
            "maximum" in error_str or
            "too long" in error_str or
            "length" in error_str
        )

        if is_overflow:
            # 激进压缩后重试
            compacted = self.compact(messages, aggressive=True)
            return compacted, True

        return messages, False

    # ========== 后处理 (Post Run) ==========

    def after_run(self, messages: list, had_error: bool = False) -> dict:
        """运行后处理"""
        self.increment_turn()

        result = {
            "actions": [],
            "context_size": self.estimate_tokens(messages),
        }

        # 检查是否需要压缩
        if self.check_should_compact(messages):
            result["actions"].append("compact")
            result["messages"] = self.compact(messages)

        # 检查是否需要反思
        if self.check_should_reflect():
            result["actions"].append("reflect")
            result["reflection"] = self.run_reflection()

        return result

    # ========== 记忆系统 ==========

    def record_task(self, task: dict) -> None:
        """记录任务"""
        self.task_history.append({**task, "timestamp": time.time()})

        if task.get("status") == "completed":
            self.completed_tasks.append({**task, "timestamp": time.time()})
            self.metrics.tasks_completed += 1

            if self.config.memory_on_task_complete:
                self._auto_save_memory(task)

    def _auto_save_memory(self, task: dict) -> None:
        """自动保存任务记忆"""
        subject = task.get("subject", "Unknown task")
        content = f"""## 任务完成: {subject}

- 完成时间: {time.strftime('%Y-%m-%d %H:%M')}
- 状态: {task.get('status', 'unknown')}

描述: {task.get('description', 'N/A')}
"""
        self.memory_manager.save(
            name=f"task_{int(time.time())}",
            description=subject,
            mem_type="project",
            content=content,
        )

    def save_memory(self, name: str, description: str, mem_type: str, content: str) -> str:
        """保存记忆"""
        return self.memory_manager.save(name, description, mem_type, content)

    def list_memory(self) -> list:
        """列出所有记忆"""
        return self.memory_manager.list_all()

    # ========== 自我反思 ==========

    def check_should_reflect(self) -> bool:
        """检查是否应该运行反思"""
        if not self.config.reflect_on_idle:
            return False
        turn_number = self.metrics.total_turns
        since_last = turn_number - self.metrics.last_reflect_turn
        return since_last >= self.config.reflect_interval

    def run_reflection(self) -> dict:
        """运行自我反思"""
        self.metrics.last_reflect_turn = self.metrics.total_turns

        patterns = [f"完成 {len(self.task_history)} 个任务"]

        should_create_skill, pattern = self._should_create_skill()

        return {
            "action": "reflect",
            "patterns": patterns,
            "should_create_skill": should_create_skill,
            "skill_pattern": pattern,
        }

    def _should_create_skill(self) -> tuple[bool, Optional[str]]:
        """检查是否应该创建技能"""
        task_types = {}
        for task in self.task_history:
            task_type = task.get("type", "unknown")
            task_types[task_type] = task_types.get(task_type, 0) + 1

        for task_type, count in task_types.items():
            if count >= 3:
                return True, task_type

        return False, None

    # ========== 统计 ==========

    def increment_turn(self) -> None:
        """增加对话轮次"""
        self.metrics.total_turns += 1

    def get_summary(self) -> dict:
        """获取会话摘要"""
        return {
            "total_turns": self.metrics.total_turns,
            "tasks_completed": self.metrics.tasks_completed,
            "tools_called": self.metrics.total_tools_called,
            "compact_count": self.metrics.compact_count,
            "output_saved": self.metrics.output_saved_count,
            "session_duration": int(time.time() - self.metrics.session_start),
        }

    def reset(self) -> None:
        """重置会话"""
        self.metrics = SessionMetrics()
        self.task_history.clear()
        self.completed_tasks.clear()


# 全局实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager() -> None:
    """重置全局会话管理器"""
    global _session_manager
    _session_manager = None