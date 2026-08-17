from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .practices import PracticeSpec, known_practice_keys


@dataclass(frozen=True)
class TopicPoint:
    """One teaching point inside a knowledge-bank topic."""

    id: str
    point: str
    explanation: str
    evidence_wording: str
    forbidden_strengthenings: tuple[str, ...]
    fit_practices: tuple[str, ...]
    return_hint: str


@dataclass(frozen=True)
class KnowledgeTopic:
    """One request category in the knowledge bank (anxiety, sleep, ...)."""

    id: str
    name: str
    safety_notes: str
    points: tuple[TopicPoint, ...]


@dataclass(frozen=True)
class KnowledgeBank:
    """The full knowledge bank loaded from content/knowledge-bank.json."""

    topics: tuple[KnowledgeTopic, ...]

    def topic(self, topic_id: str) -> KnowledgeTopic:
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        raise ValueError(f"unknown knowledge-bank topic: {topic_id}")


@dataclass(frozen=True)
class TopicBrief:
    """The one-off writing brief: a topic plus its selected teaching points.

    Replaces TeachingBrief selection in the one-off path. The course path
    keeps using TeachingBrief; this brief is built from knowledge-bank.json
    for one-off requests (topic id/name, 1-3 teaching points, the practice's
    exact return cue, and the situation string).
    """

    topic_id: str
    topic_name: str
    points: tuple[TopicPoint, ...]
    return_cue: str
    situation: str


def load_knowledge_bank(content_root: Path) -> KnowledgeBank:
    """Load and validate content/knowledge-bank.json.

    Raises ValueError on a malformed bank so a broken data file can never
    silently produce an unwritten brief.
    """
    raw = json.loads(
        (content_root / "knowledge-bank.json").read_text(encoding="utf-8")
    )
    if not isinstance(raw, dict) or not isinstance(raw.get("topics"), list):
        raise ValueError("knowledge-bank.json must contain a 'topics' list")

    topics: list[KnowledgeTopic] = []
    point_ids: set[str] = set()
    for item in raw["topics"]:
        if not isinstance(item, dict):
            raise ValueError("each knowledge-bank topic must be an object")
        topic_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        safety_notes = str(item.get("safety_notes") or "").strip()
        raw_points = item.get("points")
        if not topic_id or not name or not isinstance(raw_points, list):
            raise ValueError(
                f"knowledge-bank topic is missing id, name, or points: {item!r}"
            )
        points: list[TopicPoint] = []
        for point_item in raw_points:
            if not isinstance(point_item, dict):
                raise ValueError(
                    f"knowledge-bank point for topic {topic_id!r} must be an object"
                )
            point_id = str(point_item.get("id") or "").strip()
            point = str(point_item.get("point") or "").strip()
            explanation = str(point_item.get("explanation") or "").strip()
            evidence_wording = str(point_item.get("evidence_wording") or "").strip()
            forbidden = tuple(
                str(entry).strip()
                for entry in point_item.get("forbidden_strengthenings", [])
                if str(entry).strip()
            )
            fit = tuple(
                str(entry).strip()
                for entry in point_item.get("fit_practices", [])
                if str(entry).strip()
            )
            return_hint = str(point_item.get("return_hint") or "").strip()
            if not point_id or not point or not explanation or not fit:
                raise ValueError(
                    f"knowledge-bank point {point_id!r} in topic {topic_id!r} "
                    "is missing id, point, explanation, or fit_practices"
                )
            if point_id in point_ids:
                raise ValueError(
                    f"knowledge-bank point identifiers must be unique: {point_id}"
                )
            point_ids.add(point_id)
            points.append(
                TopicPoint(
                    id=point_id,
                    point=point,
                    explanation=explanation,
                    evidence_wording=evidence_wording,
                    forbidden_strengthenings=forbidden,
                    fit_practices=fit,
                    return_hint=return_hint,
                )
            )
        topics.append(
            KnowledgeTopic(
                id=topic_id,
                name=name,
                safety_notes=safety_notes,
                points=tuple(points),
            )
        )
    if not topics:
        raise ValueError("knowledge-bank.json contains no topics")
    return KnowledgeBank(topics=tuple(topics))


def auto_pick_practice(
    bank: KnowledgeBank,
    topic_id: str,
    situation: str = "",
    *,
    llm_call: Callable | None = None,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> str:
    """Return an engine practice a topic's points fit.

    Bank keys that have no engine practice yet (sound_awareness,
    open_awareness, daily_life) are skipped. When a situation is supplied
    and an llm_call is given, the model judges the best practice from the
    topic's available set; if the call or its answer fails, the keyword
    nudge below is used instead: bed/night/lying toward sleep, walk/outdoors
    toward walking, people/social toward loving kindness when the topic fits
    it, otherwise breath anchor. The situation only nudges; the topic's
    available practices always win.
    """
    available = _fitting_engine_keys(bank, topic_id)
    if not available:
        raise ValueError(f"no engine practice fits topic {topic_id!r}")

    if llm_call is not None and situation.strip():
        chosen = _llm_judge_practice(
            bank,
            topic_id,
            situation,
            available,
            llm_call=llm_call,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        if chosen is not None:
            return chosen

    return _nudge_practice(bank, topic_id, situation, available)


def _fitting_engine_keys(bank: KnowledgeBank, topic_id: str) -> set[str]:
    engine_keys = set(known_practice_keys())
    return {
        key
        for point in bank.topic(topic_id).points
        for key in point.fit_practices
        if key in engine_keys
    }


def _llm_judge_practice(
    bank: KnowledgeBank,
    topic_id: str,
    situation: str,
    available: set[str],
    *,
    llm_call: Callable,
    api_key: str,
    base_url: str,
    model: str,
) -> str | None:
    """Ask the cheap model to choose the best practice for the situation.

    Returns a validated engine practice key, or None on any failure so the
    caller falls back to the deterministic nudge.
    """
    topic = bank.topic(topic_id)
    system_prompt = (
        "You choose which meditation practice best fits a person's situation. "
        "Answer with STRICT JSON only: {\"practice\": \"<key>\"}."
    )
    user_prompt = (
        f"Topic: {topic.name} ({topic_id}).\n"
        f"Situation: {situation}\n"
        f"Allowed practices: {', '.join(sorted(available))}\n\n"
        "Pick the single practice that best matches the person's energy, posture, "
        "and need right now. Consider safety: if the person is distressed, choose a "
        "grounding practice; if tired or in bed, choose rest; if outdoors, choose "
        "walking. Reply with only the JSON object."
    )
    try:
        raw = llm_call(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        data = json.loads(_extract_json_object(raw))
        chosen = str(data.get("practice") or "").strip()
    except Exception:
        return None
    if chosen not in available:
        return None
    return chosen


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _nudge_practice(
    bank: KnowledgeBank,
    topic_id: str,
    situation: str,
    available: set[str],
) -> str:
    """Keyword-based practice choice used when no LLM judge is available."""

    def _first_key(*preferred: str) -> str | None:
        for key in preferred:
            if key in available:
                return key
        return None

    situation_lower = situation.lower()
    nudged = None
    has_word = lambda *words: any(
        re.search(rf"\b{re.escape(word)}\b", situation_lower) for word in words
    )
    if has_word("bed", "lying", "night"):
        nudged = _first_key("sleep", "body_scan", "breath_anchor")
    elif has_word("walk", "walking", "outdoor", "outside", "path"):
        nudged = _first_key("walking", "breath_anchor")
    elif has_word("people", "social", "party", "crowd", "group", "event"):
        nudged = _first_key("loving_kindness", "breath_anchor")

    if nudged is not None:
        return nudged

    # Fall back to the topic's first fitting practice in bank order.
    topic = bank.topic(topic_id)
    engine_keys = set(known_practice_keys())
    for point in topic.points:
        for key in point.fit_practices:
            if key in engine_keys:
                return key
    raise ValueError(f"no engine practice fits topic {topic_id!r}")


def select_topic_brief(
    bank: KnowledgeBank,
    *,
    topic_id: str,
    spec: PracticeSpec,
    minutes: int,
    situation: str = "",
    recent_point_ids: Sequence[str] = (),
) -> TopicBrief:
    """Build a one-off TopicBrief from the knowledge bank.

    Selects 1-3 teaching points that fit the practice (1 for short sessions,
    2 for medium, 3 for long), avoiding recently used points when enough
    choices exist. The exact return method always comes from the practice
    spec, so a walker never gets a breath-return cue.
    """
    topic = bank.topic(topic_id)
    fitting = [point for point in topic.points if spec.key in point.fit_practices]
    if not fitting:
        fits = sorted({key for point in topic.points for key in point.fit_practices})
        raise ValueError(
            f"no teaching points in topic {topic_id!r} fit practice "
            f"{spec.key!r}; fits: {', '.join(fits)}"
        )
    if minutes <= 5:
        max_points = 1
    elif minutes <= 10:
        max_points = 2
    else:
        max_points = 3
    recent = set(recent_point_ids)
    fresh = [point for point in fitting if point.id not in recent]
    pool = fresh or fitting
    selected = random.sample(pool, min(max_points, len(pool)))
    order = {point.id: index for index, point in enumerate(topic.points)}
    selected = tuple(sorted(selected, key=lambda point: order[point.id]))
    return TopicBrief(
        topic_id=topic.id,
        topic_name=topic.name,
        points=selected,
        return_cue=spec.return_cue,
        situation=situation.strip(),
    )
