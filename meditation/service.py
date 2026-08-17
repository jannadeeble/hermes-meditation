from __future__ import annotations

import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .curriculum import load_foundation_course
from .knowledge_bank import (
    TopicBrief,
    auto_pick_practice,
    load_knowledge_bank,
    select_topic_brief,
)
from .practices import PracticeSpec, practice_spec
from .publisher import PublishedFile
from .renderer import MeditationRenderer, audio_duration
from .script_writer import ScriptWriter, WrittenScript
from .storage import SessionStore
from .teaching import (
    TeachingBrief,
    course_teaching_brief,
)


class Publisher(Protocol):
    def publish(self, file_path: Path, display_name: str) -> PublishedFile: ...


class VoiceProvider(Protocol):
    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        delivery: str = "grounding",
        practice: str | None = None,
    ) -> Path: ...


class Writer(Protocol):
    def write(
        self,
        spec: PracticeSpec,
        *,
        minutes: int,
        theme: str | None = None,
        teaching: TeachingBrief | None = None,
        topic: TopicBrief | None = None,
    ) -> WrittenScript: ...


class GenerationResult:
    def __init__(self, *, session_id: str, session_dir: Path, published: PublishedFile) -> None:
        self.session_id = session_id
        self.session_dir = session_dir
        self.published = published


DEFAULT_SOUNDSCAPE = "data/files/Nervous System Reset  432 Hz + Theta Wave Ambient Meditation Music for Deep Calm.mp3"


def _resolve_soundscape(
    *,
    content_root: Path,
    soundscape_root: Path | None,
    soundscape: str | None,
    target_seconds: float,
) -> tuple[Path | None, float | None]:
    """Resolve a lesson soundscape to an on-disk path and a random start offset."""
    if not soundscape:
        return None, None
    if soundscape_root is None:
        content_dir = content_root.resolve()
        soundscape_root = content_dir.parents[2]
    soundscape_path = soundscape_root / soundscape
    if not soundscape_path.exists():
        raise ValueError(f"soundscape file not found: {soundscape}")
    soundscape_seconds = audio_duration(soundscape_path)
    max_start = max(0.0, soundscape_seconds - target_seconds)
    soundscape_start_seconds = random.uniform(0.0, max_start)
    return soundscape_path, soundscape_start_seconds


def generate_foundation_session(
    *,
    day: int,
    minutes: int,
    content_root: Path,
    store: SessionStore,
    voice: VoiceProvider,
    publisher: Publisher,
    session_id: str | None = None,
    soundscape_root: Path | None = None,
    writer: Writer | None = None,
    theme: str | None = None,
) -> GenerationResult:
    if minutes < 1 or minutes > 60:
        raise ValueError("minutes must be between 1 and 60")
    course = load_foundation_course(content_root)
    lesson = course.renderable_lesson(day)
    if minutes < lesson.min_session_minutes:
        raise ValueError(
            f"foundation course day {day} supports at least {lesson.min_session_minutes} minute sessions"
        )
    if minutes > lesson.max_session_minutes:
        raise ValueError(
            f"foundation course day {day} supports at most {lesson.max_session_minutes} minute sessions"
        )
    if writer is not None:
        spec = practice_spec(lesson.practice)
        teaching = course_teaching_brief(content_root, lesson, spec)
        written = writer.write(
            spec,
            minutes=minutes,
            theme=theme,
            teaching=teaching,
        )
        blocks = written.blocks
        resolved_theme = written.theme
        script_source = "llm"
    else:
        blocks = lesson.blocks_for_minutes(minutes)
        resolved_theme = None
        script_source = "saved"
        teaching = course_teaching_brief(
            content_root,
            lesson,
            practice_spec(lesson.practice),
        )
    resolved_session_id = session_id or (
        f"foundation-30-day-{day:02d}-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    manifest = {
        "session_id": resolved_session_id,
        "course_id": course.course_id,
        "day": lesson.day,
        "title": lesson.title,
        "objective": lesson.objective,
        "practice": lesson.practice,
        "voice_provider": getattr(voice, "provider_name", "unknown"),
        "minutes": minutes,
        "evidence_card_ids": list(lesson.evidence_card_ids),
        "soundscape": lesson.soundscape,
        "script_source": script_source,
        "theme": resolved_theme,
        "teaching_card_id": teaching.id,
        "teaching_title": teaching.title,
        "status": "rendering",
        "created_at": datetime.now(UTC).isoformat(),
    }
    session_dir = store.create_session(resolved_session_id, manifest)
    renderer = MeditationRenderer(
        voice,
        speech_tempo=lesson.speech_tempo,
        practice=lesson.practice,
    )
    soundscape_path, soundscape_start_seconds = _resolve_soundscape(
        content_root=content_root,
        soundscape_root=soundscape_root,
        soundscape=lesson.soundscape,
        target_seconds=float(minutes * 60),
    )
    rendered = renderer.render(
        blocks,
        opening_silence_seconds=lesson.opening_silence_seconds,
        target_seconds=float(minutes * 60),
        output_dir=session_dir,
        soundscape=soundscape_path,
        soundscape_start_seconds=soundscape_start_seconds,
    )
    score = {
        "target_seconds": minutes * 60,
        "opening_silence_seconds": rendered.opening_silence_seconds,
        "speech_tempo": lesson.speech_tempo,
        "speech_seconds": list(rendered.speech_seconds),
        "pause_seconds": list(rendered.pause_seconds),
        "soundscape": lesson.soundscape,
        "soundscape_start_seconds": rendered.soundscape_start_seconds,
        "soundscape_volume": rendered.soundscape_volume,
        "script_source": script_source,
        "theme": resolved_theme,
        "blocks": [
            {
                "text": block.text,
                "pause_instruction": block.pause_instruction,
                "pause_min_seconds": block.pause_min_seconds,
                "pause_weight": block.pause_weight,
                "min_minutes": block.min_minutes,
                "delivery": block.delivery,
                "stage": block.stage,
            }
            for block in blocks
        ],
    }
    (session_dir / "score.json").write_text(
        json.dumps(score, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    display_name = f"foundation-day-{day:02d}-{lesson.title.lower().replace(' ', '-')}.mp3"
    published = publisher.publish(rendered.mp3_path, display_name)
    manifest.update(
        {
            "status": "ready",
            "wav_path": str(rendered.wav_path),
            "mp3_path": str(rendered.mp3_path),
            "published_url": published.viewer_url,
            "raw_url": published.raw_url,
            "completed_at": datetime.now(UTC).isoformat(),
        }
    )
    store.write_manifest(resolved_session_id, manifest)
    return GenerationResult(session_id=resolved_session_id, session_dir=session_dir, published=published)


def generate_one_off_session(
    *,
    topic: str,
    minutes: int,
    content_root: Path,
    store: SessionStore,
    voice: VoiceProvider,
    publisher: Publisher,
    writer: Writer,
    practice: str | None = None,
    theme: str | None = None,
    situation: str = "",
    session_id: str | None = None,
    soundscape_root: Path | None = None,
    soundscape: str | None = DEFAULT_SOUNDSCAPE,
) -> GenerationResult:
    """Generate a fresh, LLM-written meditation for a knowledge-bank topic.

    This is the flexible path: the user names a topic (anxiety, sleep, stress,
    ...) and an optional practice, and the writer produces a new themed
    script every time from the topic's teaching points. When the practice is
    omitted, the first practice the topic fits is chosen.
    """
    if minutes < 1 or minutes > 60:
        raise ValueError("minutes must be between 1 and 60")
    bank = load_knowledge_bank(content_root)
    if practice is None:
        practice = auto_pick_practice(
            bank,
            topic,
            situation=situation,
            llm_call=getattr(writer, "llm_call", None),
            api_key=getattr(writer, "api_key", ""),
            base_url=getattr(writer, "base_url", ""),
            model=getattr(writer, "model", ""),
        )
    spec = practice_spec(practice)
    brief = select_topic_brief(
        bank,
        topic_id=topic,
        spec=spec,
        minutes=minutes,
        situation=situation,
        recent_point_ids=store.recent_topic_point_ids(),
    )
    written = writer.write(
        spec,
        minutes=minutes,
        theme=theme,
        topic=brief,
    )
    resolved_session_id = session_id or (
        f"one-off-{spec.key}-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    manifest = {
        "session_id": resolved_session_id,
        "course_id": None,
        "day": None,
        "title": spec.name,
        "objective": f"One-off {spec.name.lower()} on {brief.topic_name} with theme {written.theme!r}.",
        "practice": spec.key,
        "topic_id": brief.topic_id,
        "topic_name": brief.topic_name,
        "point_ids": [point.id for point in brief.points],
        "situation": brief.situation,
        "voice_provider": getattr(voice, "provider_name", "unknown"),
        "minutes": minutes,
        "evidence_card_ids": [],
        "soundscape": soundscape,
        "script_source": "llm",
        "theme": written.theme,
        "status": "rendering",
        "created_at": datetime.now(UTC).isoformat(),
    }
    session_dir = store.create_session(resolved_session_id, manifest)
    renderer = MeditationRenderer(voice, speech_tempo=1.0, practice=spec.key)
    soundscape_path, soundscape_start_seconds = _resolve_soundscape(
        content_root=content_root,
        soundscape_root=soundscape_root,
        soundscape=soundscape,
        target_seconds=float(minutes * 60),
    )
    rendered = renderer.render(
        written.blocks,
        opening_silence_seconds=5.0,
        target_seconds=float(minutes * 60),
        output_dir=session_dir,
        soundscape=soundscape_path,
        soundscape_start_seconds=soundscape_start_seconds,
    )
    score = {
        "target_seconds": minutes * 60,
        "opening_silence_seconds": rendered.opening_silence_seconds,
        "speech_tempo": 1.0,
        "speech_seconds": list(rendered.speech_seconds),
        "pause_seconds": list(rendered.pause_seconds),
        "soundscape": soundscape,
        "soundscape_start_seconds": rendered.soundscape_start_seconds,
        "soundscape_volume": rendered.soundscape_volume,
        "script_source": "llm",
        "theme": written.theme,
        "topic_id": brief.topic_id,
        "topic_name": brief.topic_name,
        "point_ids": [point.id for point in brief.points],
        "retried": written.retried,
        "blocks": [
            {
                "text": block.text,
                "pause_instruction": block.pause_instruction,
                "pause_min_seconds": block.pause_min_seconds,
                "pause_weight": block.pause_weight,
                "min_minutes": block.min_minutes,
                "delivery": block.delivery,
                "stage": block.stage,
            }
            for block in written.blocks
        ],
    }
    (session_dir / "score.json").write_text(
        json.dumps(score, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    theme_slug = re.sub(r"[^a-z0-9]+", "-", written.theme.lower()).strip("-")[:40]
    display_name = f"one-off-{spec.key}-{theme_slug}.mp3"
    published = publisher.publish(rendered.mp3_path, display_name)
    manifest.update(
        {
            "status": "ready",
            "wav_path": str(rendered.wav_path),
            "mp3_path": str(rendered.mp3_path),
            "published_url": published.viewer_url,
            "raw_url": published.raw_url,
            "completed_at": datetime.now(UTC).isoformat(),
        }
    )
    store.write_manifest(resolved_session_id, manifest)
    return GenerationResult(session_id=resolved_session_id, session_dir=session_dir, published=published)
