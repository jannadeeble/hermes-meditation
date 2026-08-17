from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib import request, error as urlerror

from .delivery import known_delivery_keys
from .knowledge_bank import TopicBrief
from .models import ScriptBlock
from .practices import PracticeSpec
from .teaching import TeachingBrief
from .validation import validate_script

DEEPSEEK_BASE_URL = os.getenv("MEDITATION_LLM_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.getenv("MEDITATION_LLM_MODEL", "deepseek-v4-flash")
HERMES_ENV_PATH = Path(os.getenv("HERMES_ENV_PATH", str(Path.home() / ".hermes" / ".env")))
KNOWLEDGE_BANK_PATH = (
    Path(__file__).resolve().parents[1] / "content" / "knowledge-bank.md"
)

_STAGE_ARC = (
    "arrival",
    "teaching",
    "practice",
    "wandering_return",
    "deepening",
    "integration",
    "closing",
)


@dataclass(frozen=True)
class WrittenScript:
    blocks: tuple[ScriptBlock, ...]
    theme: str
    retried: bool
    retry_problems: tuple[str, ...] = ()


class LlmCall(Protocol):
    def __call__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str: ...


def _load_api_key(env_path: Path = HERMES_ENV_PATH) -> str:
    """Return DEEPSEEK_API_KEY from the process env or the Hermes .env file."""
    value = os.getenv("DEEPSEEK_API_KEY")
    if value:
        return value.strip()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    raise RuntimeError(
        "DEEPSEEK_API_KEY not found in environment or Hermes .env"
    )


def default_llm_call(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.9,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"LLM API network error: {exc.reason}") from exc

    data = json.loads(raw)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"LLM response missing content: {raw[:300]}") from exc


_SYSTEM_PROMPT = """You write guided meditation scripts for a spoken course. The audio is voiced by a calm British male narrator and played with a quiet ambient soundscape underneath. Your output is read aloud, then timed to an exact session length. The system that speaks your script controls all the silences, so you never choose timing values: you choose only what is said and how it is delivered.

Every script MUST follow these hard rules:
1. Plain, direct, conversational English. Write the way a calm, kind friend talks you through something, not the way a scripted app narrates. No poetry, no mysticism, no "energy", no chakras, no clichés about waves washing worries away, no metaphors ("the breath is a doorway", "breathing of the sea"), no aphorisms ("the heart of the practice", "too little effort becomes drifting"). Use everyday words. Say concretely what to do and what to feel: name the body part, the sensation, the place where attention rests. The theme is a plain, literal sensory detail, mentioned at most twice ("rain on the window"); it is never a metaphor and never the star of the script.
2. Ground the teaching in what is known about attention: attention wanders many times a minute; noticing the wandering is itself the skill; returning to the chosen object, again and again, is the practice being trained. You may state this plainly. Do not promise medical or permanent effects, and do not demand a blank mind.
3. One to three teaching points, one main practice, and one quiet, plain theme detail. The supplied teaching brief or topic brief is the source of truth. Explain each selected idea plainly before applying it.
4. Each block is ONE short spoken sentence. Aim for 6 to 12 words, never more than 15. You may keep a comma inside a sentence where a pause naturally falls (a list, or two halves of one sentence); the reader will pause longer at each comma. Do not chain more than two clauses in one line. Short blocks are what create the calm rhythm.
5. Ordinary lines are followed by a fixed gap of silence. You do not need to think about it.
6. You decide where the longer pauses go and how long each one is. A long pause MUST be preceded by a clear spoken instruction telling the listener what to attend to or practise during the silence. Mark exactly that block with a "pause_instruction" and set "pause_seconds" to the number of seconds you want. The system honours your exact value, so choose it to help fill the session. The block text and pause_instruction are both spoken, so they MUST be different sentences with different jobs. Never repeat or closely paraphrase one as the other. Never place a long pause directly after a welcome, explanation, or teaching statement.
7. Open with a single short welcome ("Welcome."). There is already five seconds of silence before the first word, so do not describe opening silence.
8. Gently set up posture, hands, shoulders, face, and the choice between closed eyes and a soft open gaze (unless the practice rules say otherwise).
9. Give a short, calm overview of the practice before asking the listener to begin it.
10. Do NOT use course-position wording: no "first lesson", "second lesson", "day 1", "lesson 3", "the course", "beginner", "foundation".
11. End with a short, settled close that connects the practice to ordinary life.

Voice. The listener should feel chatted to by a soft, real voice, not lectured by a script. Write the way you would speak to one person over tea: warm, direct, plain, a little informal. Prefer "you" and short, ordinary sentences. Avoid the voice of a meditation app: no inspirational maxims, no "let us", no poetic flourishes, no abstract nouns doing the work ("the heart of the practice", "carry this balance with you", "the workable middle"). Give precise, concrete guidance about what to notice and what to do next. One idea per line. If a line sounds like something a poster would say, rewrite it as something a friend would say.

Shape a gentle performance arc instead of using one flat voice throughout. Every block MUST include one "delivery" value chosen from this list:
- "settling": the welcome and early arrival, quiet, warm, and gentle
- "grounding": clear teaching and steady anchor guidance
- "spacious": softer, more open practice instructions before silence
- "encouraging": warm, gentle reassurance when attention wanders and returns
- "brightening": a small lift in energy as the listener returns to the room or walk
- "closing": warm, settled final lines with a sense of completion
Use at least three different delivery values in a script. Begin with "settling" and end with "closing". Change delivery when the purpose of the words changes, not merely to alternate labels. Keep the whole arc calm, soft, and soothing: warm, gentle, unhurried, with no sudden lift in energy. Never use shouting, alarm, sadness, theatrical drama, or non-verbal sounds.

For the sleep practice only, the delivery is even more restricted: never use "brightening", and use "encouraging" at most as a quiet, warm reassurance with no lift at all (no energy, no rising pitch). Every sleep line should sound drowsy and unhurried.

Return STRICT JSON only, with this exact shape:
{"blocks": [{"text": "...", "pause_instruction": null, "pause_seconds": null, "delivery": "settling", "stage": "arrival"}, ...]}
- "text" is the spoken line. One short sentence, 6 to 15 words.
- "pause_instruction" is set ONLY on practice-pause blocks: a clear spoken instruction telling the listener what to do during the coming silence. Every block with a pause_instruction MUST be one the listener can follow silently (attend to the steps, the breath, a body region, a phrase). Use 2 to 4 such blocks.
- "pause_seconds" is set ONLY on those same practice-pause blocks: the exact number of seconds of silence you want after the block. The system honours your value exactly. Leave it null on ordinary lines.
- "delivery" is one of the six delivery values above.
- "stage" is one of: arrival, teaching, practice, wandering_return, deepening, integration, closing. Use every stage, once and in that exact order. A stage may contain several adjacent blocks.
- End with a short close.
"""


def _writing_limits(minutes: int) -> tuple[int, int, int, int, int, int]:
    if minutes <= 2:
        return 4, 6, 1, 10, 20, max(60, minutes * 36)
    if minutes <= 5:
        return minutes + 3, minutes * 2 + 2, 2, 20, 40, minutes * 36
    if minutes <= 10:
        return round(minutes * 1.5), round(minutes * 2.4), 3, 25, 60, minutes * 36
    if minutes <= 20:
        return round(minutes * 1.4), round(minutes * 1.8), 4, 30, 90, minutes * 36
    return round(minutes * 1.2), round(minutes * 1.6), 4, 30, 120, minutes * 36


_ARC_INSTRUCTIONS = """Required arc. Label every block with its stage and keep these stages in order:
1. arrival: settle the body and explain the practice ahead.
2. teaching: state the one idea plainly, then explain why it matters.
3. practice: apply the idea to the attention target before the first silence.
4. wandering_return: explain what to do when attention moves, using the exact return method.
5. deepening: continue the same practice with less guidance and no new teaching.
6. integration: connect the learned move to the daily-life use or the situation named for this session.
7. closing: widen attention and end simply."""


def _knowledge_bank_section(bank_text: str) -> str:
    return (
        "\n\nThe Meditation Knowledge Bank below is the complete source of knowledge"
        " for every session. Read the whole document before writing. Everything you"
        " say must be grounded in it, and its topics (Part 3) list the teaching"
        " points a session may use.\n\n"
        + bank_text
    )


def build_user_prompt(
    spec: PracticeSpec,
    theme: str,
    minutes: int,
    *,
    teaching: TeachingBrief | None = None,
    topic: TopicBrief | None = None,
) -> str:
    cue_list = ", ".join(spec.cue_vocabulary)
    forbidden = ", ".join(spec.forbidden_cues) if spec.forbidden_cues else "none"
    extra = "\n".join(f"- {rule}" for rule in spec.extra_rules)
    min_blocks, max_blocks, practice_pauses, pause_min, pause_max, max_words = _writing_limits(minutes)
    if teaching is not None:
        teaching_section = f"""
Teaching brief:
- Title: {teaching.title}
- One idea to teach: {teaching.teaching_point}
- Approved explanation: {teaching.explanation}
- Exact return method: {teaching.return_cue}
- Daily-life use: {teaching.daily_life_application}

{_ARC_INSTRUCTIONS}
"""
    elif topic is not None:
        points = "\n".join(
            f"{index}. {point.point} — {point.explanation}"
            for index, point in enumerate(topic.points, start=1)
        )
        situation = (
            f"- Situation: {topic.situation}"
            if topic.situation
            else "- Situation: none named; connect the practice to an ordinary moment in the day"
        )
        teaching_section = f"""
Topic brief:
- Topic: {topic.topic_name} (id: {topic.topic_id})
{situation}
- Teaching points (state each one plainly, then explain it):
{points}
- Exact return method: {topic.return_cue}

{_ARC_INSTRUCTIONS}
"""
    else:
        teaching_section = ""
    return f"""Write a {minutes}-minute guided meditation.

Practice: {spec.name}
Posture: {spec.posture}
Attention target: {spec.attention_target}
Theme: {theme}
{teaching_section}

Use this cue vocabulary naturally, where it fits:
{cue_list}

Forbidden cues for this practice:
{forbidden}

Practice-specific rules:
{extra}

Length budget:
- Use {min_blocks}-{max_blocks} blocks in total.
- Include exactly {practice_pauses} practice pauses with spoken instructions.
- You choose where the longer pauses go and how long each one is. Set "pause_seconds" on those practice-pause blocks to the exact seconds you want (between {pause_min} and {pause_max} seconds each). The system honours your value exactly, so pick pauses that help fill the session. Longer sessions need longer or more pauses to feel full; leaving time unused makes the session end in quiet.
- Use no more than {max_words} spoken words in total, including pause instructions.
- Leave enough room for silence. Do not fill the requested time with speech.

Write fresh, warm, specific words, as if you were talking to one person. Mention the theme no more than twice, as a plain, literal detail, never as a metaphor. Do not invent current weather, time, or surroundings. Do not reuse wording from any previous script you may have seen. No inspirational maxims, no aphorisms, no poetic turns of phrase. Preserve the distinction between noticing a thought and returning attention, and pushing thoughts out or making them disappear. Do not tell the listener to let a thought go, to drop it, or to empty the mind. Thoughts come and go on their own; the practice is noticing and coming back."""


class ScriptWriter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEFAULT_MODEL,
        llm_call: Callable[..., str] = default_llm_call,
        env_path: Path = HERMES_ENV_PATH,
        knowledge_bank_path: Path = KNOWLEDGE_BANK_PATH,
    ) -> None:
        # Resolve lazily at write time so tests can construct a writer
        # without a key and only fail when an actual call is attempted.
        self._api_key = api_key
        self.base_url = base_url
        self.model = model
        self.llm_call = llm_call
        self.env_path = env_path
        self.knowledge_bank_path = knowledge_bank_path

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return _load_api_key(self.env_path)

    def _knowledge_bank_text(self) -> str:
        try:
            return self.knowledge_bank_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"knowledge bank not found at {self.knowledge_bank_path}; "
                "the writer must always see the whole bank"
            ) from exc

    def write(
        self,
        spec: PracticeSpec,
        *,
        minutes: int,
        theme: str | None = None,
        teaching: TeachingBrief | None = None,
        topic: TopicBrief | None = None,
    ) -> WrittenScript:
        if teaching is not None and topic is not None:
            raise ValueError("pass only one of teaching (course) or topic (one-off)")
        requested_theme = bool(theme and theme.strip())
        resolved_theme = spec.pick_theme(theme)
        user_prompt = build_user_prompt(
            spec,
            resolved_theme,
            minutes,
            teaching=teaching,
            topic=topic,
        )
        # The whole knowledge bank is force-read on every write call: the
        # writer always sees the complete document, never a selection of it.
        system_prompt = _SYSTEM_PROMPT + _knowledge_bank_section(
            self._knowledge_bank_text()
        )
        raw = self.llm_call(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        blocks, problems = self._parse_and_validate(
            raw,
            spec,
            resolved_theme,
            minutes=minutes,
            check_theme_mention=requested_theme,
            require_arc=teaching is not None or topic is not None,
            teaching=teaching,
        )
        if problems:
            # One retry with the problems fed back, then surface the failure.
            retry_prompt = (
                user_prompt
                + "\n\nYour previous draft was rejected for these reasons:\n- "
                + "\n- ".join(problems)
                + "\n\nRewrite it fixing every reason. Keep the same theme and length."
            )
            raw = self.llm_call(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
            )
            blocks, retry_problems = self._parse_and_validate(
                raw,
                spec,
                resolved_theme,
                minutes=minutes,
                check_theme_mention=requested_theme,
                require_arc=teaching is not None or topic is not None,
                teaching=teaching,
            )
            if retry_problems:
                raise ValueError(
                    "generated meditation failed validation twice: "
                    + "; ".join(retry_problems)
                )
            return WrittenScript(
                blocks=blocks,
                theme=resolved_theme,
                retried=True,
                retry_problems=tuple(problems),
            )
        return WrittenScript(
            blocks=blocks,
            theme=resolved_theme,
            retried=False,
        )

    def _parse_and_validate(
        self,
        raw: str,
        spec: PracticeSpec,
        theme: str,
        *,
        minutes: int,
        check_theme_mention: bool,
        require_arc: bool,
        teaching: TeachingBrief | None,
    ) -> tuple[tuple[ScriptBlock, ...], list[str]]:
        payload = _extract_json_object(raw)
        try:
            data = json.loads(payload)
            raw_blocks = data["blocks"]
        except (ValueError, KeyError, TypeError) as exc:
            return (), [f"response is not valid JSON with a blocks array: {str(exc)[:200]}"]

        blocks: list[ScriptBlock] = []
        parse_problems: list[str] = []
        for index, item in enumerate(raw_blocks):
            if not isinstance(item, dict):
                parse_problems.append(f"block {index} is not an object")
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                parse_problems.append(f"block {index} has no text")
                continue
            instruction = item.get("pause_instruction")
            if instruction is None:
                pause_instruction = None
            elif isinstance(instruction, str) and instruction.strip():
                pause_instruction = instruction.strip()
            else:
                parse_problems.append(
                    f"block {index} has a pause_instruction that is not a spoken string"
                )
                continue
            # The LLM may choose where the longer pauses go and how long each
            # one is. Ordinary lines keep the fixed gap and the welcome keeps
            # its 3.0s gap; only an instructed practice pause may be
            # long. The LLM's exact pause_seconds is honored (weight 0, so the
            # silence allocator does not inflate it arbitrarily). A long
            # pause_seconds still requires a spoken instruction.
            pause_seconds_raw = item.get("pause_seconds")
            if pause_seconds_raw is None or pause_seconds_raw == "":
                pause_seconds = None
            else:
                try:
                    pause_seconds = float(pause_seconds_raw)
                except (TypeError, ValueError):
                    parse_problems.append(
                        f"block {index} has a pause_seconds that is not a number"
                    )
                    continue
                if pause_seconds < 0 or pause_seconds > 120:
                    parse_problems.append(
                        f"block {index} has a pause_seconds outside the allowed range (0 to 120)"
                    )
                    continue
                if pause_seconds > 8 and not pause_instruction:
                    parse_problems.append(
                        f"block {index} has a long pause_seconds without a spoken instruction"
                    )
                    continue
            is_practice_pause = bool(pause_instruction)
            is_welcome = index == 0 and text.lower().startswith("welcome")
            if pause_seconds is not None and pause_seconds > 0:
                pause_min_seconds = pause_seconds
                pause_weight = 0.0
            elif is_practice_pause:
                pause_min_seconds = 25.0
                pause_weight = 1.0
            elif is_welcome:
                pause_min_seconds = 3.0
                pause_weight = 0.0
            else:
                pause_min_seconds = 4.5
                pause_weight = 0.0
            delivery = str(item.get("delivery", "")).strip()
            if not delivery:
                parse_problems.append(f"block {index} has no delivery")
                continue
            stage = str(item.get("stage", "")).strip()
            if require_arc and not stage:
                parse_problems.append(f"block {index} has no stage")
                continue
            if not stage:
                stage = "practice"
            try:
                blocks.append(
                    ScriptBlock(
                        text=text,
                        pause_min_seconds=pause_min_seconds,
                        pause_weight=pause_weight,
                        pause_instruction=pause_instruction,
                        min_minutes=1,
                        delivery=delivery,
                        stage=stage,
                    )
                )
            except ValueError as exc:
                parse_problems.append(f"block {index}: {exc}")

        if parse_problems:
            return tuple(blocks), parse_problems

        problems = validate_script(tuple(blocks), spec, require_arc=require_arc)
        problems.extend(_validate_delivery_arc(tuple(blocks)))
        problems.extend(_validate_duration_fit(tuple(blocks), minutes))
        if require_arc:
            problems.extend(_validate_stage_arc(tuple(blocks)))
        # Theme presence check: the chosen theme (or a core word of it) should
        # appear at least once in the spoken text when the caller named it.
        if check_theme_mention and not _theme_mentioned(tuple(blocks), theme):
            problems.append(f"the theme '{theme}' does not appear anywhere in the script")
        return tuple(blocks), problems


def _extract_json_object(raw: str) -> str:
    """Pull the JSON object out of an LLM response that may carry fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _theme_mentioned(blocks: tuple[ScriptBlock, ...], theme: str) -> bool:
    words = re.findall(r"[a-z']+", theme.lower())
    words = [w for w in words if len(w) > 3]
    if not words:
        return True
    spoken = " ".join(block.text for block in blocks).lower()
    return any(word in spoken for word in words)


def _validate_stage_arc(blocks: tuple[ScriptBlock, ...]) -> list[str]:
    compressed: list[str] = []
    for block in blocks:
        if not compressed or compressed[-1] != block.stage:
            compressed.append(block.stage)
    if tuple(compressed) != _STAGE_ARC:
        return [
            "stage arc must use every stage once and in order: "
            + ", ".join(_STAGE_ARC)
            + f"; got: {', '.join(compressed)}"
        ]
    return []


def _validate_delivery_arc(blocks: tuple[ScriptBlock, ...]) -> list[str]:
    if not blocks:
        return []
    problems: list[str] = []
    if blocks[0].delivery != "settling":
        problems.append("delivery arc must begin with 'settling'")
    if blocks[-1].delivery != "closing":
        problems.append("delivery arc must end with 'closing'")
    if len(blocks) >= 5 and len({block.delivery for block in blocks}) < 3:
        allowed = ", ".join(known_delivery_keys())
        problems.append(
            "delivery arc is too flat; use at least three delivery values from: "
            + allowed
        )
    return problems


def _validate_duration_fit(
    blocks: tuple[ScriptBlock, ...], minutes: int
) -> list[str]:
    if not blocks:
        return []
    _, max_blocks, max_practice_pauses, _, _, max_words = _writing_limits(minutes)
    problems: list[str] = []
    practice_pauses = sum(1 for block in blocks if block.pause_min_seconds >= 20)
    spoken = " ".join(
        part
        for block in blocks
        for part in (block.text, block.pause_instruction or "")
    )
    word_count = len(re.findall(r"[A-Za-z']+", spoken))
    target_seconds = minutes * 60.0
    estimated_required = (
        5.0
        + sum(block.pause_min_seconds for block in blocks)
        + word_count * 0.7
    )

    if len(blocks) > max_blocks:
        problems.append(
            f"script will not fit {minutes} minutes: {len(blocks)} blocks exceeds {max_blocks}"
        )
    if practice_pauses > max_practice_pauses:
        problems.append(
            f"script will not fit {minutes} minutes: {practice_pauses} practice pauses exceeds {max_practice_pauses}"
        )
    if word_count > max_words:
        problems.append(
            f"script will not fit {minutes} minutes: {word_count} spoken words exceeds {max_words}"
        )
    if estimated_required > target_seconds * 0.9:
        problems.append(
            f"script will not fit {minutes} minutes with enough silence: estimated minimum is {estimated_required:.0f} seconds"
        )
    return problems
