from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .models import FoundationLesson
from .practices import PracticeSpec


@dataclass(frozen=True)
class TeachingCard:
    id: str
    title: str
    teaching_point: str
    explanation: str
    practice_keys: tuple[str, ...]
    daily_life_application: str


@dataclass(frozen=True)
class TeachingBrief:
    id: str
    title: str
    teaching_point: str
    explanation: str
    return_cue: str
    daily_life_application: str
    evidence_card_ids: tuple[str, ...] = ()


def load_teaching_cards(content_root: Path) -> tuple[TeachingCard, ...]:
    raw = json.loads(
        (content_root / "teaching-cards.json").read_text(encoding="utf-8")
    )
    cards = tuple(
        TeachingCard(
            id=str(item["id"]),
            title=str(item["title"]),
            teaching_point=str(item["teaching_point"]),
            explanation=str(item["explanation"]),
            practice_keys=tuple(str(key) for key in item["practice_keys"]),
            daily_life_application=str(item["daily_life_application"]),
        )
        for item in raw["cards"]
    )
    ids = [card.id for card in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("teaching card identifiers must be unique")
    return cards


def select_teaching_card(
    cards: Sequence[TeachingCard],
    *,
    practice_key: str,
    recent_ids: Sequence[str] = (),
) -> TeachingCard:
    matching = [card for card in cards if practice_key in card.practice_keys]
    if not matching:
        raise ValueError(f"no teaching cards support practice: {practice_key}")
    recent = set(recent_ids)
    fresh = [card for card in matching if card.id not in recent]
    return random.choice(fresh or matching)


def one_off_teaching_brief(
    card: TeachingCard,
    spec: PracticeSpec,
) -> TeachingBrief:
    return TeachingBrief(
        id=card.id,
        title=card.title,
        teaching_point=card.teaching_point,
        explanation=card.explanation,
        return_cue=spec.return_cue,
        daily_life_application=card.daily_life_application,
    )


def course_teaching_brief(
    content_root: Path,
    lesson: FoundationLesson,
    spec: PracticeSpec,
) -> TeachingBrief:
    evidence_raw = json.loads(
        (content_root / "evidence-cards.json").read_text(encoding="utf-8")
    )
    evidence = {str(card["id"]): card for card in evidence_raw["cards"]}
    missing = [card_id for card_id in lesson.evidence_card_ids if card_id not in evidence]
    if missing:
        raise ValueError(
            "lesson refers to missing evidence cards: " + ", ".join(missing)
        )
    explanation = " ".join(
        str(evidence[card_id]["spoken_text"]).strip()
        for card_id in lesson.evidence_card_ids
    ).strip()
    return TeachingBrief(
        id=f"foundation-30-day-{lesson.day:02d}",
        title=lesson.title,
        teaching_point=lesson.objective,
        explanation=explanation or lesson.objective,
        return_cue=spec.return_cue,
        daily_life_application=(
            "Use the same act of noticing and returning during one ordinary moment today."
        ),
        evidence_card_ids=lesson.evidence_card_ids,
    )
