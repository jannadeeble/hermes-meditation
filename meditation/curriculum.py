from __future__ import annotations

import json
from pathlib import Path

from .models import FoundationCourse, FoundationLesson, ScriptBlock


def load_foundation_course(content_root: Path) -> FoundationCourse:
    raw = json.loads((content_root / "foundation-course.json").read_text(encoding="utf-8"))
    lessons: list[FoundationLesson] = []
    for item in raw["lessons"]:
        blocks = tuple(
            ScriptBlock(
                text=block["text"],
                pause_min_seconds=float(block["pause_min_seconds"]),
                pause_weight=float(block["pause_weight"]),
                pause_instruction=block.get("pause_instruction"),
                min_minutes=int(block.get("min_minutes", 1)),
                delivery=str(block.get("delivery", "grounding")),
                stage=str(block.get("stage", "practice")),
            )
            for block in item.get("script_blocks", [])
        )
        lessons.append(
            FoundationLesson(
                day=int(item["day"]),
                title=item["title"],
                objective=item["objective"],
                practice=item["practice"],
                status=item["status"],
                speech_tempo=float(item.get("speech_tempo", 1.0)),
                opening_silence_seconds=float(item.get("opening_silence_seconds", 0.0)),
                evidence_card_ids=tuple(item.get("evidence_card_ids", [])),
                script_blocks=blocks,
                max_session_minutes=int(item.get("max_session_minutes", 60)),
                soundscape=item.get("soundscape"),
            )
        )
    course = FoundationCourse(course_id=raw["course_id"], title=raw["title"], lessons=tuple(lessons))
    expected_days = list(range(1, 31))
    actual_days = [lesson.day for lesson in course.lessons]
    if actual_days != expected_days:
        raise ValueError("foundation course must contain ordered days 1 through 30")
    return course
