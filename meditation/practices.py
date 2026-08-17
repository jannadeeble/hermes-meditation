from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class PracticeSpec:
    """Definition of one meditation practice type.

    Carries the safety rules and cue vocabulary the LLM must follow when
    writing a fresh session, plus a themed bank the writer draws from when
    the caller does not supply a theme.
    """

    key: str
    name: str
    posture: str
    attention_target: str
    return_cue: str
    cue_vocabulary: tuple[str, ...]
    forbidden_cues: tuple[str, ...] = ()
    extra_rules: tuple[str, ...] = ()
    themes: tuple[str, ...] = ()

    def pick_theme(self, requested: str | None = None) -> str:
        if requested and requested.strip():
            return requested.strip()
        if not self.themes:
            return "stillness"
        return random.choice(self.themes)


PRACTICES: dict[str, PracticeSpec] = {
    "walking": PracticeSpec(
        key="walking",
        name="Walking with attention",
        posture="walking",
        attention_target="the ground under each foot and the rhythm of your steps",
        return_cue="Notice the wandering, then return to the next step you can feel.",
        cue_vocabulary=(
            "steps",
            "step",
            "ground",
            "under each foot",
            "pace",
            "your own pace",
            "heel",
            "toe",
            "weight moving",
            "gaze ahead, soft",
            "arms hanging",
            "shoulders",
            "walking",
        ),
        forbidden_cues=(
            "sit",
            "chair",
            "close your eyes",
            "floor beneath you",
            "cross your legs",
            "cushion",
            "lying down",
        ),
        extra_rules=(
            "Keep every cue compatible with walking. The listener is standing and moving, not sitting or lying.",
            "Do not add stock walking warnings (no fear-of-falling or terrain warnings).",
            "The practice is noticing attention wandering and returning it to the next step or the ground contact.",
        ),
        themes=(
            "a cool morning on a quiet road",
            "the pavement after light rain",
            "an empty street in early light",
            "the short walk to the shop",
            "a footpath between houses",
            "the road home in the evening",
            "a level path through a park",
            "the strip of ground by the wall",
        ),
    ),
    "breath_anchor": PracticeSpec(
        key="breath_anchor",
        name="Breath anchor",
        posture="seated",
        attention_target="the natural coming and going of the breath",
        return_cue="Notice the wandering, then return gently to the next breath you can feel.",
        cue_vocabulary=(
            "breath",
            "breathing",
            "in",
            "out",
            "rising",
            "falling",
            "natural breath",
            "nostrils",
            "chest",
            "belly",
            "one breath",
            "attention wanders and returns",
        ),
        forbidden_cues=(
            "hold your breath",
            "breathe in deeply",
            "force",
            "count the breath",
            "breathe faster",
            "breathwork",
            "pranayama",
        ),
        extra_rules=(
            "Natural breathing only. No breath holds, no forced slow rate, no rapid breathing, no counting games.",
            "The practice is noticing when attention wanders and returning it to the next breath.",
        ),
        themes=(
            "a kitchen in the early evening",
            "the window while rain runs down it",
            "a bus stop at the end of the day",
            "the corner of a quiet room",
            "a park bench in plain daylight",
            "the porch with the light on",
            "a shelf of books in a warm room",
            "the stretch of floor by the window",
        ),
    ),
    "body_scan": PracticeSpec(
        key="body_scan",
        name="Body awareness",
        posture="seated",
        attention_target="sensation moving through the body, one region at a time",
        return_cue="Notice where attention went, then return to the body region you were feeling.",
        cue_vocabulary=(
            "feet",
            "legs",
            "hips",
            "belly",
            "chest",
            "shoulders",
            "arms",
            "hands",
            "jaw",
            "face",
            "scalp",
            "warmth",
            "weight",
            "contact",
            "sensation",
        ),
        forbidden_cues=(
            "hold your breath",
            "breathe in deeply",
            "force",
            "tense up",
            "tighten",
            "clench",
        ),
        extra_rules=(
            "Move attention through the body in a clear order, spending a few quiet moments in each region.",
            "Invite noticing sensation exactly as it is. Never ask the listener to force relaxation or tense muscles.",
        ),
        themes=(
            "the chair you are sitting in",
            "the floor under your feet",
            "a room at the end of the day",
            "the weight of a coat on your shoulders",
            "the light on the wall beside you",
            "a familiar doorway in your home",
            "the quiet between two rooms",
            "the view from your usual seat",
        ),
    ),
    "loving_kindness": PracticeSpec(
        key="loving_kindness",
        name="Kindness practice",
        posture="seated",
        attention_target="a repeated phrase of goodwill directed at yourself and then others",
        return_cue="Notice that attention moved, then return gently to the goodwill phrase.",
        cue_vocabulary=(
            "may I be safe",
            "may I be well",
            "may I be at ease",
            "kindness",
            "goodwill",
            "warmth",
            "a person you care for",
            "a stranger",
            "all beings",
        ),
        forbidden_cues=(
            "hold your breath",
            "force",
            "guilt",
            "should feel",
            "must love",
        ),
        extra_rules=(
            "Use short repeated phrases of goodwill, beginning with yourself, then someone you care for, then widening.",
            "Never imply the listener must feel a certain way. Offer the phrases gently and without demand.",
        ),
        themes=(
            "the people who share your day",
            "someone you spoke to this morning",
            "the person behind the counter",
            "a neighbour who waves",
            "the ones who raised you",
            "a friend who listens",
            "a stranger on the same road",
            "the person you were yesterday",
        ),
    ),
    "sleep": PracticeSpec(
        key="sleep",
        name="Rest and sleep",
        posture="lying",
        attention_target="letting the body settle, one part at a time, without effort",
        return_cue="Notice that attention moved, then return to the body's contact with the bed.",
        cue_vocabulary=(
            "settle",
            "heavy",
            "soft",
            "release",
            "rest",
            "bed",
            "pillow",
            "blanket",
            "dark",
            "quiet",
            "letting go",
            "slowing",
        ),
        forbidden_cues=(
            "stay awake",
            "fight sleep",
            "focus hard",
            "concentrate",
            "hold your breath",
        ),
        extra_rules=(
            "The listener is lying down, possibly in bed. Keep cues gentle and drowsy; nothing alerting or effortful.",
            "The aim is rest and settling, not a task to succeed at. If sleep comes, that is welcome; if not, resting is enough.",
        ),
        themes=(
            "the last errand of the day",
            "the hour before the house goes quiet",
            "a room with the lights turned low",
            "the slow end of a long day",
            "the walk from the door to the bed",
            "a house settling into the night",
            "the moment the day is done",
            "the dark behind your closed eyes",
        ),
    ),
    "focus": PracticeSpec(
        key="focus",
        name="Steady attention",
        posture="seated",
        attention_target="a single chosen object of attention, returning each time it drifts",
        return_cue="Notice the drift, then return gently to the object you chose.",
        cue_vocabulary=(
            "choose",
            "one thing",
            "attention",
            "drift",
            "wander",
            "return",
            "again",
            "steady",
            "notice",
            "begin again",
        ),
        forbidden_cues=(
            "hold your breath",
            "strain",
            "force",
            "don't think",
            "empty your mind",
        ),
        extra_rules=(
            "Invite the listener to choose one simple object of attention and return to it each time the mind wanders.",
            "Wandering is expected and is part of the practice, never a failure. Do not demand a blank mind.",
        ),
        themes=(
            "one task you can finish",
            "the page you are reading",
            "a single word you like",
            "the pen in your hand",
            "the one thing on the desk",
            "the next small step",
            "a number you can hold in mind",
            "the sentence you just read",
        ),
    ),
}


def practice_spec(key: str) -> PracticeSpec:
    normalized = key.strip().lower()
    if normalized not in PRACTICES:
        raise ValueError(
            f"unknown practice type: {key}. Known types: {', '.join(sorted(PRACTICES))}"
        )
    return PRACTICES[normalized]


def known_practice_keys() -> Sequence[str]:
    return tuple(sorted(PRACTICES))
