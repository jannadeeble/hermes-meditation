from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import ScriptBlock
from .practices import PracticeSpec

_COURSE_POSITION_RE = re.compile(
    r"\b(first lesson|second lesson|day \d+|lesson \d+|the course)\b",
    re.IGNORECASE,
)

_MAX_BLOCK_WORDS = 15
_NEAR_DUPLICATE_THRESHOLD = 0.88

_WOO_WORDS = (
    "energy field",
    "chakra",
    "vibration",
    "align your",
    "universe",
    "cosmic",
    "divine",
    "sacred",
    "manifest",
    "awaken",
    "higher self",
    "inner light",
    "spiritual energy",
    "breathe in the light",
    "universal",
    "frequency",
)

# Distinctive anchor each practice's return cue names (sleep -> bed,
# walking -> step, ...). A script that returns to a different practice's
# anchor in its wandering_return stage is a wrong return cue; a paraphrase
# of the practice's own anchor is fine and never matched here.
_PRACTICE_ANCHOR_TERMS: dict[str, tuple[str, ...]] = {
    "walking": ("step",),
    "breath_anchor": ("breath",),
    "body_scan": ("body region",),
    "loving_kindness": ("goodwill",),
    "sleep": ("bed", "mattress", "pillow"),
    "focus": ("chosen object", "object you chose"),
}

# Sleep and rest must never push energy up: "brightening" is forbidden.
_SLEEP_FORBIDDEN_DELIVERY = "brightening"


def validate_script(
    blocks: tuple[ScriptBlock, ...],
    spec: PracticeSpec,
    *,
    require_arc: bool = False,
) -> list[str]:
    """Return a list of rule problems for an LLM-written script.

    An empty list means the script is safe to render. The checks mirror the
    content rules the course lessons must satisfy, applied to a generated
    script: practice-appropriate cues, no forbidden cues, every long pause
    with a spoken instruction, and no course-position wording. When
    ``require_arc`` is true the light topic checks also run: the teaching
    stage must carry spoken text, and the wandering return must not name
    another practice's anchor.
    """
    problems: list[str] = []

    if not blocks:
        problems.append("script has no blocks")
        return problems

    spoken = " ".join(block.text for block in blocks).lower()
    instructions = " ".join(
        (block.pause_instruction or "") for block in blocks if block.pause_instruction
    ).lower()
    full_text = f"{spoken} {instructions}"

    # Practice cues present
    if not any(cue in full_text for cue in spec.cue_vocabulary):
        problems.append(
            f"script does not use any of the {spec.key} cue vocabulary: "
            + ", ".join(spec.cue_vocabulary[:5])
        )

    # Forbidden cues absent
    for cue in spec.forbidden_cues:
        if cue.lower() in full_text:
            problems.append(
                f"script uses a cue forbidden for {spec.key}: '{cue}'"
            )

    # Extra practice-specific rules
    problems.extend(_apply_extra_rules(blocks, spec))

    # Every long or weighted pause must carry a spoken instruction
    for index, block in enumerate(blocks):
        if (block.pause_weight > 0 or block.pause_min_seconds > 8) and not (
            block.pause_instruction and block.pause_instruction.strip()
        ):
            problems.append(
                f"block {index} has a long/weighted pause without a spoken instruction: "
                + block.text[:60]
            )

    # A pause instruction is spoken after the block text. If they are the
    # same line, the listener hears the sentence twice before the silence.
    for index, block in enumerate(blocks):
        instruction = (block.pause_instruction or "").strip()
        if instruction and _normalise_spoken(block.text) == _normalise_spoken(instruction):
            problems.append(
                f"block {index} repeats its text as the pause instruction"
            )

    # Reject close paraphrases across all spoken parts. Short phrases such as
    # "Welcome" are ignored because similarity is not meaningful there.
    spoken_parts: list[tuple[str, str]] = []
    for index, block in enumerate(blocks):
        spoken_parts.append((f"block {index} text", block.text))
        if block.pause_instruction:
            spoken_parts.append(
                (f"block {index} pause instruction", block.pause_instruction)
            )
    for left_index, (left_label, left_text) in enumerate(spoken_parts):
        left = _normalise_spoken(left_text)
        if len(left.split()) < 6:
            continue
        for right_label, right_text in spoken_parts[left_index + 1 :]:
            right = _normalise_spoken(right_text)
            if len(right.split()) < 6 or left == right:
                continue
            if SequenceMatcher(None, left, right).ratio() >= _NEAR_DUPLICATE_THRESHOLD:
                problems.append(
                    f"{left_label} and {right_label} are near-duplicate spoken lines"
                )

    # No course-position wording in spoken audio
    if _COURSE_POSITION_RE.search(spoken):
        problems.append("script uses course-position wording (day number, lesson number, 'the course')")

    # Opening must begin with the welcome convention. The welcome is its own
    # short block so the reader gets a real gap after it before the first line.
    first_text = blocks[0].text.strip()
    if not first_text.lower().startswith("welcome"):
        problems.append(
            f"script must open with a short welcome, got: {first_text[:40]!r}"
        )
    welcome_word_count = len(re.findall(r"[A-Za-z']+", first_text))
    if welcome_word_count > 2:
        problems.append(
            f"the welcome must be its own short line (e.g. \"Welcome.\"), got: {first_text[:60]!r}"
        )

    # Each block is one short spoken sentence (keeps the rhythm and gaps)
    for index, block in enumerate(blocks):
        word_count = len(re.findall(r"[A-Za-z']+", block.text))
        if word_count > _MAX_BLOCK_WORDS:
            problems.append(
                f"block {index} is too long for one spoken line: {word_count} words "
                f"(max {_MAX_BLOCK_WORDS}). Split it into shorter blocks."
            )

    # Plain, science-grounded language: no woo-woo phrasing
    for phrase in _WOO_WORDS:
        if phrase in full_text:
            problems.append(
                f"script uses woo-woo phrasing: '{phrase}'. Rewrite it in plain, "
                "science-grounded language."
            )

    # Sleep and rest never push energy up, so "brightening" is forbidden
    # for the sleep practice before any voice credit is spent.
    if spec.key == "sleep" and any(
        block.delivery == _SLEEP_FORBIDDEN_DELIVERY for block in blocks
    ):
        problems.append(
            f"the {spec.key} practice cannot use the "
            f"'{_SLEEP_FORBIDDEN_DELIVERY}' delivery"
        )

    # Light topic checks (only meaningful when the stage arc is required).
    if require_arc:
        problems.extend(_teaching_stage_problems(blocks))
        problems.extend(_wrong_return_cue_problems(blocks, spec))

    return problems


def _teaching_stage_problems(blocks: tuple[ScriptBlock, ...]) -> list[str]:
    """The teaching stage must be present and carry at least one spoken line."""
    teaching_blocks = [block for block in blocks if block.stage == "teaching"]
    if not teaching_blocks:
        return ["script has no teaching stage"]
    if not any(block.text.strip() for block in teaching_blocks):
        return ["the teaching stage has no spoken text"]
    return []


def _wrong_return_cue_problems(
    blocks: tuple[ScriptBlock, ...], spec: PracticeSpec
) -> list[str]:
    """Reject a wandering return that names another practice's anchor.

    The practice's own anchor (e.g. sleep -> bed, walking -> step) may be
    paraphrased freely; only a return that points at a *different*
    practice's anchor is a wrong return cue.
    """
    own_terms = set(_PRACTICE_ANCHOR_TERMS.get(spec.key, ()))
    other_terms: list[tuple[str, str]] = [
        (term, key)
        for key, terms in _PRACTICE_ANCHOR_TERMS.items()
        if key != spec.key
        for term in terms
        if term not in own_terms
    ]
    if not other_terms:
        return []
    wander_parts: list[str] = []
    for block in blocks:
        if block.stage != "wandering_return":
            continue
        wander_parts.append(block.text)
        if block.pause_instruction:
            wander_parts.append(block.pause_instruction)
    wander_text = " ".join(wander_parts).lower()
    if not wander_text:
        return []
    problems: list[str] = []
    for term, other_key in other_terms:
        if re.search(rf"\b{re.escape(term)}\b", wander_text):
            problems.append(
                f"wandering return names the {other_key} anchor '{term}'; "
                f"for {spec.key}, return to {spec.return_cue}"
            )
    return problems


def _normalise_spoken(text: str) -> str:
    return " ".join(re.findall(r"[a-z']+", text.lower()))


def _apply_extra_rules(
    blocks: tuple[ScriptBlock, ...], spec: PracticeSpec
) -> list[str]:
    problems: list[str] = []
    full_spoken = " ".join(
        part
        for block in blocks
        for part in (block.text, block.pause_instruction or "")
    ).lower()
    for rule in spec.extra_rules:
        if "wandering" in rule and "wander" not in full_spoken:
            problems.append("script does not mention attention wandering (core of the practice)")
    return problems
