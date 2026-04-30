"""自我提升机制 - 自动触发

触发条件:
1. 周期性 - 每完成 N 个任务
2. 失败时 - 任务失败立即分析
3. 模式检测 - 重复模式出现 3+ 次
4. 手动触发 - /dream 命令
5. 退出时 - 会话结束时总结
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


WORKDIR = Path.cwd()
STORAGE_DIR = WORKDIR / ".minicode"
MEMORY_DIR = STORAGE_DIR / ".memory"
SKILLS_DIR = STORAGE_DIR / "skills"


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    description: str
    success: bool
    duration: float  # 秒
    error: str = ""
    task_type: str = "general"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ImprovementTrigger:
    """触发条件"""
    trigger_type: str  # periodic, failure, pattern, manual, exit
    reason: str
    timestamp: float = field(default_factory=time.time)


class SelfImprovementEngine:
    """自我提升引擎

    自动检测触发条件，执行自我提升
    """

    def __init__(
        self,
        periodic_interval: int = 10,  # 每 N 个任务触发一次
        pattern_threshold: int = 3,     # 模式出现 N 次触发
        idle_threshold: int = 300,      # 空闲 N 秒触发
    ):
        self.periodic_interval = periodic_interval
        self.pattern_threshold = pattern_threshold
        self.idle_threshold = idle_threshold

        # 任务历史
        self.task_history: list[TaskRecord] = []

        # 模式计数
        self.pattern_counts: dict[str, int] = {}

        # 触发记录
        self.trigger_history: list[ImprovementTrigger] = []

        # 最后活动时刻
        self._last_activity = time.time()

        # 创建必要目录
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def record_task(self, task: TaskRecord) -> ImprovementTrigger | None:
        """记录任务，检测是否触发自我提升"""
        self.task_history.append(task)
        self._last_activity = time.time()

        trigger = None

        # 1. 检查周期性触发
        if len(self.task_history) % self.periodic_interval == 0:
            trigger = ImprovementTrigger(
                trigger_type="periodic",
                reason=f"完成了 {len(self.task_history)} 个任务",
            )

        # 2. 检查失败触发
        elif not task.success and task.error:
            trigger = ImprovementTrigger(
                trigger_type="failure",
                reason=f"任务失败: {task.error[:50]}",
            )

        # 3. 检查模式触发
        pattern = self._extract_pattern(task)
        if pattern:
            self.pattern_counts[pattern] = self.pattern_counts.get(pattern, 0) + 1
            if self.pattern_counts[pattern] >= self.pattern_threshold:
                trigger = ImprovementTrigger(
                    trigger_type="pattern",
                    reason=f"检测到重复模式: {pattern} ({self.pattern_counts[pattern]}次)",
                )
                # 重置计数，避免重复触发
                self.pattern_counts[pattern] = 0

        if trigger:
            self.trigger_history.append(trigger)
            return trigger

        return None

    def _extract_pattern(self, task: TaskRecord) -> str | None:
        """从任务中提取模式"""
        # 简单模式提取：基于任务类型
        if task.task_type and task.task_type != "general":
            return task.task_type

        # 基于关键词
        keywords = ["bug", "refactor", "test", "deploy", "config", "docs"]
        for kw in keywords:
            if kw in task.description.lower():
                return kw

        return None

    def should_trigger_idle(self) -> bool:
        """检查空闲触发"""
        if not self.task_history:
            return False

        idle_time = time.time() - self._last_activity
        if idle_time > self.idle_threshold:
            return True
        return False

    def trigger_manual(self) -> ImprovementTrigger:
        """手动触发"""
        trigger = ImprovementTrigger(
            trigger_type="manual",
            reason="用户手动触发",
        )
        self.trigger_history.append(trigger)
        return trigger

    def trigger_exit(self) -> ImprovementTrigger:
        """退出时触发"""
        trigger = ImprovementTrigger(
            trigger_type="exit",
            reason=f"会话结束，共 {len(self.task_history)} 个任务",
        )
        self.trigger_history.append(trigger)
        return trigger

    # ========== 整合分析 ==========

    def analyze(self, trigger: ImprovementTrigger) -> dict:
        """执行自我提升分析"""
        result = {
            "trigger": trigger.trigger_type,
            "timestamp": trigger.timestamp,
            "patterns": [],
            "suggestions": [],
            "created_skills": [],
            "saved_memories": [],
        }

        if trigger.trigger_type == "periodic":
            # 周期性分析：总结最近的任务
            recent = self.task_history[-self.periodic_interval:]
            result["patterns"] = self._analyze_patterns(recent)
            result["suggestions"] = self._suggest_improvements(recent)

        elif trigger.trigger_type == "failure":
            # 失败分析：重点关注错误
            recent = self.task_history[-5:]
            failures = [t for t in recent if not t.success]
            result["suggestions"] = self._analyze_failures(failures)
            # 保存错误教训
            for t in failures:
                self._save_failure_lesson(t)

        elif trigger.trigger_type == "pattern":
            # 模式分析：创建技能
            pattern = self._get_trigger_pattern(trigger.reason)
            if pattern:
                skill = self._create_skill_from_pattern(pattern)
                if skill:
                    result["created_skills"].append(skill)

        elif trigger.trigger_type in ("manual", "exit"):
            # 全面分析
            result["patterns"] = self._analyze_patterns(self.task_history)
            result["suggestions"] = self._suggest_improvements(self.task_history)

        # 保存经验记忆
        if result["patterns"] or result["suggestions"]:
            memory = self._save_experience(result)
            result["saved_memories"].append(memory)

        return result

    def _analyze_patterns(self, tasks: list[TaskRecord]) -> list[str]:
        """分析成功模式"""
        patterns = []
        success_tasks = [t for t in tasks if t.success]

        if not success_tasks:
            return patterns

        # 按类型统计
        by_type: dict[str, int] = {}
        for t in success_tasks:
            by_type[t.task_type] = by_type.get(t.task_type, 0) + 1

        for task_type, count in by_type.items():
            if count >= 2:
                patterns.append(f"{task_type} 类型任务成功率较高")

        # 平均耗时
        avg_duration = sum(t.duration for t in success_tasks) / len(success_tasks)
        patterns.append(f"平均任务耗时: {avg_duration:.1f}秒")

        return patterns

    def _suggest_improvements(self, tasks: list[TaskRecord]) -> list[str]:
        """建议改进"""
        suggestions = []

        failures = [t for t in tasks if not t.success]
        if failures:
            suggestions.append(f"有 {len(failures)} 个失败任务需要关注")

        slow_tasks = [t for t in tasks if t.duration > 300]  # > 5分钟
        if slow_tasks:
            suggestions.append(f"有 {len(slow_tasks)} 个任务耗时较长 (>5分钟)")

        return suggestions

    def _analyze_failures(self, failures: list[TaskRecord]) -> list[str]:
        """分析失败原因"""
        suggestions = []

        for t in failures:
            if "permission" in t.error.lower():
                suggestions.append(f"权限问题: {t.description}")
            elif "timeout" in t.error.lower():
                suggestions.append(f"超时问题: {t.description}")
            elif "not found" in t.error.lower():
                suggestions.append(f"资源不存在: {t.description}")
            else:
                suggestions.append(f"未知错误: {t.error[:50]}")

        return suggestions

    def _get_trigger_pattern(self, reason: str) -> str | None:
        """从原因中提取模式"""
        for pattern in self.pattern_counts.keys():
            if pattern in reason:
                return pattern
        return None

    def _create_skill_from_pattern(self, pattern: str) -> str | None:
        """从模式创建技能"""
        # 收集该模式的任务
        related_tasks = [
            t for t in self.task_history
            if pattern in t.description.lower() or t.task_type == pattern
        ]

        if len(related_tasks) < 3:
            return None

        # 生成技能内容
        skill_content = f"""# 技能: {pattern}

## 模式说明
从 {len(related_tasks)} 个任务中提取的经验

## 成功经验
"""

        success_tasks = [t for t in related_tasks if t.success]
        for t in success_tasks[:3]:
            skill_content += f"- {t.description}\n"

        skill_content += f"""
## 注意事项
"""

        failure_tasks = [t for t in related_tasks if not t.success]
        for t in failure_tasks[:3]:
            skill_content += f"- 避免: {t.description} ({t.error})\n"

        skill_content += f"""
## 创建时间
{time.strftime('%Y-%m-%d %H:%M')}
"""

        # 保存技能
        skill_file = SKILLS_DIR / f"{pattern}_{int(time.time())}.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        return f"创建技能: {pattern}"

    def _save_failure_lesson(self, task: TaskRecord) -> str:
        """保存失败教训"""
        lesson = f"""## 失败教训

任务: {task.description}
时间: {time.strftime('%Y-%m-%d %H:%M', time.localtime(task.timestamp))}
错误: {task.error}

### 分析
{self._analyze_failures([task])}

### 教训
记住这个错误，避免类似问题
"""
        lesson_file = MEMORY_DIR / f"lesson_{int(time.time())}.md"
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        lesson_file.write_text(lesson, encoding="utf-8")

        return f"保存教训: {task.task_id}"

    def _save_experience(self, analysis: dict) -> str:
        """保存经验"""
        experience = f"""## 经验总结

触发类型: {analysis['trigger']}
时间: {time.strftime('%Y-%m-%d %H:%M', time.localtime(analysis['timestamp']))}

### 发现的模式
"""
        for p in analysis.get("patterns", []):
            experience += f"- {p}\n"

        experience += "\n### 改进建议\n"
        for s in analysis.get("suggestions", []):
            experience += f"- {s}\n"

        exp_file = MEMORY_DIR / f"experience_{int(time.time())}.md"
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        exp_file.write_text(experience, encoding="utf-8")

        return f"保存经验"

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "total_tasks": len(self.task_history),
            "success_count": len([t for t in self.task_history if t.success]),
            "failure_count": len([t for t in self.task_history if not t.success]),
            "patterns_detected": len(self.pattern_counts),
            "improvements_triggered": len(self.trigger_history),
            "last_activity": self._last_activity,
        }


# 全局实例
_self_improvement: Optional[SelfImprovementEngine] = None


def get_self_improvement() -> SelfImprovementEngine:
    """获取全局自我提升引擎"""
    global _self_improvement
    if _self_improvement is None:
        _self_improvement = SelfImprovementEngine()
    return _self_improvement


def reset_self_improvement() -> None:
    """重置自我提升引擎"""
    global _self_improvement
    _self_improvement = None
