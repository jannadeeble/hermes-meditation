from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .delivery import delivery_direction


@dataclass(frozen=True)
class ScriptBlock:
    text: str
    pause_min_seconds: float
    pause_weight: float
    pause_instruction: str | None = None
    min_minutes: int = 1
    delivery: str = "grounding"
    stage: str = "practice"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("script block text is required")
        if self.pause_min_seconds < 0:
            raise ValueError("pause minimum cannot be negative")
        if self.pause_weight < 0:
            raise ValueError("pause weight cannot be negative")
        if self.min_minutes < 1:
            raise ValueError("minimum session length cannot be below one minute")
        delivery_direction(self.delivery)
        instruction = (self.pause_instruction or "").strip()
        if (self.pause_weight > 0 or self.pause_min_seconds > 8) and not instruction:
            raise ValueError("a long or weighted pause requires a spoken instruction")

    @property
    def spoken_text(self) -> str:
        instruction = (self.pause_instruction or "").strip()
        if not instruction:
            return self.text.strip()
        return f"{self.text.strip()} {instruction}"


@dataclass(frozen=True)
class FoundationLesson:
    day: int
    title: str
    objective: str
    practice: str
    status: str
    speech_tempo: float
    opening_silence_seconds: float
    evidence_card_ids: tuple[str, ...]
    script_blocks: tuple[ScriptBlock, ...]
    max_session_minutes: int = 60
    soundscape: str | None = None

    @property
    def min_session_minutes(self) -> int:
        return min(block.min_minutes for block in self.script_blocks)

    def blocks_for_minutes(self, minutes: int) -> tuple[ScriptBlock, ...]:
        if minutes < self.min_session_minutes:
            raise ValueError(
                f"foundation course day {self.day} supports at least {self.min_session_minutes} minute sessions"
            )
        return tuple(block for block in self.script_blocks if block.min_minutes <= minutes)


@dataclass(frozen=True)
class FoundationCourse:
    course_id: str
    title: str
    lessons: tuple[FoundationLesson, ...]

    def lesson(self, day: int) -> FoundationLesson:
        for lesson in self.lessons:
            if lesson.day == day:
                return lesson
        raise ValueError(f"unknown foundation course day: {day}")

    def renderable_lesson(self, day: int) -> FoundationLesson:
        lesson = self.lesson(day)
        if lesson.status != "ready":
            raise ValueError(f"foundation course day {day} is not ready")
        return lesson


@dataclass(frozen=True)
class RenderResult:
    wav_path: Path
    mp3_path: Path
    speech_seconds: tuple[float, ...]
    pause_seconds: tuple[float, ...]
    opening_silence_seconds: float
    soundscape_start_seconds: float | None = None
    soundscape_volume: float | None = None
