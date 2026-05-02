"""Evolution engine - self-improvement through experience."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class EvolutionTrigger(Enum):
    """Trigger for evolution analysis."""

    TASK_COMPLETE = "task_complete"  # After successful task
    TASK_FAILED = "task_failed"  # After failed task
    PATTERN_DETECTED = "pattern_detected"  # Repeated pattern
    IDLE_REVIEW = "idle_review"  # Periodic review
    MANUAL = "manual"  # User triggered


@dataclass
class EvolutionEvent:
    """An event for evolution analysis."""

    event_type: EvolutionTrigger
    task_id: str
    description: str
    success: bool
    duration: float = 0.0  # Duration in seconds
    error: str = ""  # Error if failed
    timestamp: float = field(default_factory=datetime.now().timestamp)
    metadata: dict = field(default_factory=dict)


@dataclass
class DetectedPattern:
    """A detected pattern from task history."""

    pattern_type: str  # "bug", "refactor", "deploy", etc.
    description: str
    frequency: int  # How many times detected
    first_seen: float
    last_seen: float
    related_task_ids: list[str] = field(default_factory=list)
    suggestion: str = ""  # Suggested action


@dataclass
class SkillTemplate:
    """Template for generating skills."""

    name: str
    description: str
    trigger_keywords: list[str]  # Keywords that trigger this skill
    prompt_template: str  # Template for LLM prompt
    expected_tools: list[str] = field(default_factory=list)
    success_pattern: str = ""
    failure_pattern: str = ""


@dataclass
class EvolutionResult:
    """Result of evolution analysis."""

    trigger: EvolutionTrigger
    timestamp: float = field(default_factory=datetime.now().timestamp)
    patterns: list[DetectedPattern] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    skills_created: list[str] = field(default_factory=list)
    memories_updated: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class EvolutionEngine:
    """Self-evolution engine.

    Analyzes task history to:
    - Detect patterns
    - Create skills
    - Update memories
    - Improve future performance
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        pattern_threshold: int = 3,  # Pattern detected after N occurrences
        skill_threshold: int = 5,  # Skill created after N pattern matches
    ):
        self.storage_dir = storage_dir or Path.home() / ".minicode" / "evolution"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.pattern_threshold = pattern_threshold
        self.skill_threshold = skill_threshold

        self._event_history: list[EvolutionEvent] = []
        self._patterns: dict[str, DetectedPattern] = {}
        self._skills: dict[str, dict] = {}
        self._pattern_counts: dict[str, int] = {}

        self._stats = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "patterns_detected": 0,
            "skills_created": 0,
            "improvement_score": 0.0,
        }

        self._load_history()

    def _load_history(self) -> None:
        """Load history from disk."""
        events_file = self.storage_dir / "events.json"
        if events_file.exists():
            try:
                data = json.loads(events_file.read_text())
                self._event_history = [
                    EvolutionEvent(**e) for e in data.get("events", [])
                ]
                self._stats = data.get("stats", self._stats)
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save history to disk."""
        events_file = self.storage_dir / "events.json"
        data = {
            "events": [vars(e) for e in self._event_history[-1000:]],  # Keep last 1000
            "stats": self._stats,
        }
        events_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def record_event(self, event: EvolutionEvent) -> Optional[EvolutionTrigger]:
        """Record an event and check if evolution should be triggered."""
        self._event_history.append(event)
        self._stats["total_events"] += 1

        if event.success:
            self._stats["successful_events"] += 1
        else:
            self._stats["failed_events"] += 1
            self._analyze_failure(event)

        # Check for patterns
        trigger = self._check_patterns(event)

        # Save periodically
        if self._stats["total_events"] % 10 == 0:
            self._save_history()

        return trigger

    def _check_patterns(self, event: EvolutionEvent) -> Optional[EvolutionTrigger]:
        """Check if event triggers pattern detection."""
        # Extract pattern type from description
        pattern_type = self._extract_pattern_type(event.description)

        if not pattern_type:
            return None

        # Increment count
        count = self._pattern_counts.get(pattern_type, 0) + 1
        self._pattern_counts[pattern_type] = count

        # Check threshold
        if count >= self.pattern_threshold:
            pattern = DetectedPattern(
                pattern_type=pattern_type,
                description=f"Detected {pattern_type} pattern",
                frequency=count,
                first_seen=event.timestamp,
                last_seen=event.timestamp,
                related_task_ids=[event.task_id],
            )
            self._patterns[pattern_type] = pattern
            self._stats["patterns_detected"] += 1

            # Reset count to avoid repeated triggers
            self._pattern_counts[pattern_type] = 0

            return EvolutionTrigger.PATTERN_DETECTED

        return None

    def _extract_pattern_type(self, description: str) -> Optional[str]:
        """Extract pattern type from task description."""
        description_lower = description.lower()

        keywords = {
            "bug": ["bug", "fix", "error", "issue"],
            "refactor": ["refactor", "improve", "optimize", "clean"],
            "test": ["test", "testing", "unittest"],
            "deploy": ["deploy", "release", "publish"],
            "config": ["config", "settings", "setup"],
            "docs": ["docs", "documentation", "readme"],
        }

        for pattern_type, kws in keywords.items():
            if any(kw in description_lower for kw in kws):
                return pattern_type

        return None

    def _analyze_failure(self, event: EvolutionEvent) -> None:
        """Analyze failure and suggest improvements."""
        # Store failure for later analysis
        pass  # Could add more sophisticated analysis

    def analyze(self, trigger: EvolutionTrigger) -> EvolutionResult:
        """Perform evolution analysis based on trigger."""
        result = EvolutionResult(trigger=trigger)

        if trigger == EvolutionTrigger.PATTERN_DETECTED:
            # Get detected patterns
            result.patterns = list(self._patterns.values())

            # Generate suggestions
            for pattern in result.patterns:
                result.suggestions.append(
                    f"Consider creating a skill for {pattern.pattern_type} tasks"
                )

        elif trigger in (EvolutionTrigger.IDLE_REVIEW, EvolutionTrigger.MANUAL):
            # Full analysis
            result.patterns = list(self._patterns.values())
            result.suggestions = self._generate_suggestions()

        # Update improvement score
        self._update_improvement_score(result)

        return result

    def _generate_suggestions(self) -> list[str]:
        """Generate improvement suggestions."""
        suggestions = []

        # Based on failure rate
        if self._stats["total_events"] > 0:
            failure_rate = self._stats["failed_events"] / self._stats["total_events"]
            if failure_rate > 0.3:
                suggestions.append("High failure rate detected - consider adding error handling")

        # Based on patterns
        if self._patterns:
            for pattern in self._patterns.values():
                suggestions.append(f"Review {pattern.pattern_type} tasks for optimization")

        return suggestions

    def _update_improvement_score(self, result: EvolutionResult) -> None:
        """Update overall improvement score."""
        # Simple scoring: based on successful patterns and skills
        score = 0.0
        score += len(result.patterns) * 10
        score += len(result.skills_created) * 20
        score += (self._stats["successful_events"] / max(self._stats["total_events"], 1)) * 30

        self._stats["improvement_score"] = min(100.0, score)

    def create_skill(self, pattern_type: str, template: SkillTemplate) -> str:
        """Create a new skill from pattern."""
        skill_id = f"skill_{pattern_type}_{len(self._skills)}"
        skill_path = self.storage_dir / "skills" / f"{skill_id}.json"
        skill_path.parent.mkdir(parents=True, exist_ok=True)

        self._skills[skill_id] = {
            "id": skill_id,
            "pattern_type": pattern_type,
            "template": vars(template),
            "created_at": datetime.now().timestamp(),
        }

        skill_path.write_text(json.dumps(self._skills[skill_id], indent=2))
        self._stats["skills_created"] += 1

        return skill_id

    def get_stats(self) -> dict:
        """Get evolution statistics."""
        return {
            "total_events": self._stats["total_events"],
            "successful_events": self._stats["successful_events"],
            "failed_events": self._stats["failed_events"],
            "patterns_detected": self._stats["patterns_detected"],
            "skills_created": self._stats["skills_created"],
            "improvement_score": self._stats["improvement_score"],
            "active_patterns": len(self._patterns),
        }