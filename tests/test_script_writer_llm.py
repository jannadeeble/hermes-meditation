import json
import unittest
from pathlib import Path

from meditation.knowledge_bank import TopicBrief, TopicPoint
from meditation.practices import PRACTICES
from meditation.script_writer import ScriptWriter, _SYSTEM_PROMPT, build_user_prompt
from meditation.teaching import TeachingBrief

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

WALKING_JSON = {
    "blocks": [
        {"text": "Welcome.", "pause_instruction": None, "delivery": "settling"},
        {"text": "Walk the road at your own pace, easy and unhurried.", "pause_instruction": None, "delivery": "grounding"},
        {"text": "Feel the ground under each foot.", "pause_instruction": None, "delivery": "grounding"},
        {
            "text": "When attention wanders, bring it back to your steps.",
            "pause_instruction": "For the next little while, walk and notice the ground meeting each foot.",
            "delivery": "encouraging",
        },
        {"text": "One ordinary step can be enough.", "pause_instruction": None, "delivery": "closing"},
    ]
}


TEACHING = TeachingBrief(
    id="attention-return",
    title="Noticing is the turning point",
    teaching_point="Realising that attention wandered is already a moment of awareness.",
    explanation="The useful moment is noticing, then choosing to begin again without blame.",
    return_cue="Notice the wandering, then return to the next step you can feel.",
    daily_life_application="Use one moment of noticing before returning to an ordinary task.",
)


STAGED_WALKING_JSON = {
    "blocks": [
        {"text": "Welcome.", "pause_instruction": None, "delivery": "settling", "stage": "arrival"},
        {"text": "Walk the coast road at your own pace.", "pause_instruction": None, "delivery": "settling", "stage": "arrival"},
        {"text": "Noticing that attention wandered is already a moment of awareness.", "pause_instruction": None, "delivery": "grounding", "stage": "teaching"},
        {"text": "That moment gives you a choice to begin again.", "pause_instruction": None, "delivery": "grounding", "stage": "teaching"},
        {"text": "Let the ground under each foot become your anchor.", "pause_instruction": "During this silence, feel each step from heel to toe.", "delivery": "spacious", "stage": "practice"},
        {"text": "When attention wanders, notice it without blame.", "pause_instruction": None, "delivery": "encouraging", "stage": "wandering_return"},
        {"text": "Then return to the next step you can feel.", "pause_instruction": None, "delivery": "encouraging", "stage": "wandering_return"},
        {"text": "Now let the walking continue with less guidance.", "pause_instruction": "For this silence, stay with one step at a time.", "delivery": "spacious", "stage": "deepening"},
        {"text": "Use one such return during an ordinary task today.", "pause_instruction": None, "delivery": "brightening", "stage": "integration"},
        {"text": "Let your attention widen while you keep walking.", "pause_instruction": None, "delivery": "closing", "stage": "closing"},
    ]
}


ANXIETY_TOPIC_BRIEF = TopicBrief(
    topic_id="anxiety",
    topic_name="Anxiety",
    points=(
        TopicPoint(
            id="A1",
            point="Anxiety is a signal, not a verdict.",
            explanation="The body's alarm is built to protect.",
            evidence_wording="",
            forbidden_strengthenings=(),
            fit_practices=("breath_anchor", "body_scan", "sleep"),
            return_hint="to the body's contact with the seat, floor, or bed",
        ),
    ),
    return_cue="Notice the wandering, then return gently to the next breath you can feel.",
    situation="before a meeting",
)


ANXIETY_BREATH_JSON = {
    "blocks": [
        {"text": "Welcome.", "pause_instruction": None, "delivery": "settling", "stage": "arrival"},
        {"text": "Settle into your seat and let your shoulders drop.", "pause_instruction": None, "delivery": "settling", "stage": "arrival"},
        {"text": "Anxiety is a signal, not a verdict.", "pause_instruction": None, "delivery": "grounding", "stage": "teaching"},
        {"text": "The body's alarm is built to protect you.", "pause_instruction": None, "delivery": "grounding", "stage": "teaching"},
        {"text": "Rest your attention on the natural breath.", "pause_instruction": "During this silence, follow each breath as it comes and goes.", "delivery": "spacious", "stage": "practice"},
        {"text": "When attention wanders, notice it without blame.", "pause_instruction": None, "delivery": "encouraging", "stage": "wandering_return"},
        {"text": "Then return gently to the next breath you can feel.", "pause_instruction": None, "delivery": "encouraging", "stage": "wandering_return"},
        {"text": "Stay with the breath in a quiet room, with less guidance.", "pause_instruction": "For this silence, keep returning to the next breath.", "delivery": "spacious", "stage": "deepening"},
        {"text": "Before your meeting, one breath is enough.", "pause_instruction": None, "delivery": "brightening", "stage": "integration"},
        {"text": "Let your attention widen, and carry this into the day.", "pause_instruction": None, "delivery": "closing", "stage": "closing"},
    ]
}


def fake_llm_call(*, api_key, base_url, model, system_prompt, user_prompt):
    # Return a valid walking script; fail on the retry prompt to prove the
    # one-retry path surfaces the error.
    if "rejected" in user_prompt:
        raise AssertionError("should not retry a passing script")
    return json.dumps(WALKING_JSON)


class ScriptWriterTests(unittest.TestCase):
    def test_teaching_brief_and_full_arc_are_in_the_writing_prompt(self) -> None:
        prompt = build_user_prompt(
            PRACTICES["walking"],
            "the coast road",
            5,
            teaching=TEACHING,
        )

        self.assertIn(TEACHING.title, prompt)
        self.assertIn(TEACHING.teaching_point, prompt)
        self.assertIn(TEACHING.explanation, prompt)
        self.assertIn(TEACHING.return_cue, prompt)
        self.assertIn(TEACHING.daily_life_application, prompt)
        self.assertIn("Preserve the distinction", prompt)
        self.assertIn("Do not tell the listener to let a thought go", prompt)
        for stage in (
            "arrival",
            "teaching",
            "practice",
            "wandering_return",
            "deepening",
            "integration",
            "closing",
        ):
            self.assertIn(stage, prompt)

    def test_topic_brief_is_in_the_user_prompt(self) -> None:
        prompt = build_user_prompt(
            PRACTICES["breath_anchor"],
            "a quiet room",
            5,
            topic=ANXIETY_TOPIC_BRIEF,
        )

        self.assertIn("Topic: Anxiety (id: anxiety)", prompt)
        self.assertIn("before a meeting", prompt)
        self.assertIn("Anxiety is a signal, not a verdict.", prompt)
        self.assertIn("The body's alarm is built to protect.", prompt)
        self.assertIn(
            "return gently to the next breath you can feel",
            prompt,
        )
        self.assertIn("Preserve the distinction", prompt)
        self.assertIn("Do not tell the listener to let a thought go", prompt)
        for stage in (
            "arrival",
            "teaching",
            "practice",
            "wandering_return",
            "deepening",
            "integration",
            "closing",
        ):
            self.assertIn(stage, prompt)

    def test_system_prompt_includes_the_full_knowledge_bank(self) -> None:
        captured: dict[str, str] = {}

        def capture(*, system_prompt, **kwargs):
            captured["system_prompt"] = system_prompt
            return json.dumps(WALKING_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=capture)
        writer.write(PRACTICES["walking"], minutes=10, theme="the coast road")

        bank_text = (CONTENT_ROOT / "knowledge-bank.md").read_text(encoding="utf-8")
        self.assertIn(bank_text, captured["system_prompt"])
        # The existing writing rules must still be present alongside the bank.
        self.assertIn("You decide where the longer pauses go", captured["system_prompt"])

    def test_topic_brief_teaching_stage_reflects_the_given_point(self) -> None:
        captured: dict[str, str] = {}

        def topic_llm(*, user_prompt, **kwargs):
            captured["user_prompt"] = user_prompt
            return json.dumps(ANXIETY_BREATH_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=topic_llm)
        written = writer.write(
            PRACTICES["breath_anchor"],
            minutes=5,
            theme="a quiet room",
            topic=ANXIETY_TOPIC_BRIEF,
        )

        self.assertFalse(written.retried)
        teaching_blocks = [block for block in written.blocks if block.stage == "teaching"]
        self.assertTrue(teaching_blocks)
        self.assertTrue(
            any(
                ANXIETY_TOPIC_BRIEF.points[0].point in block.text
                for block in teaching_blocks
            )
        )
        self.assertEqual(
            tuple(dict.fromkeys(block.stage for block in written.blocks)),
            (
                "arrival",
                "teaching",
                "practice",
                "wandering_return",
                "deepening",
                "integration",
                "closing",
            ),
        )

    def test_missing_arc_is_rejected_then_rewritten_with_all_stages(self) -> None:
        calls = 0

        def unstaged_then_staged(*, user_prompt, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return json.dumps(WALKING_JSON)
            self.assertIn("stage", user_prompt.lower())
            return json.dumps(STAGED_WALKING_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=unstaged_then_staged)
        written = writer.write(
            PRACTICES["walking"],
            minutes=5,
            theme="the coast road",
            teaching=TEACHING,
        )

        self.assertTrue(written.retried)
        self.assertEqual(calls, 2)
        self.assertEqual(
            tuple(dict.fromkeys(block.stage for block in written.blocks)),
            (
                "arrival",
                "teaching",
                "practice",
                "wandering_return",
                "deepening",
                "integration",
                "closing",
            ),
        )

    def test_write_returns_validated_blocks(self) -> None:
        writer = ScriptWriter(api_key="test-key", llm_call=fake_llm_call)
        written = writer.write(PRACTICES["walking"], minutes=10, theme="the coast road")

        self.assertEqual(written.theme, "the coast road")
        self.assertFalse(written.retried)
        self.assertEqual(written.blocks[0].text, "Welcome.")
        self.assertEqual(written.blocks[0].delivery, "settling")
        self.assertEqual(written.blocks[0].pause_min_seconds, 3.0)
        self.assertEqual(written.blocks[3].delivery, "encouraging")
        self.assertTrue(written.blocks[3].pause_instruction)
        self.assertEqual(written.blocks[3].pause_weight, 1.0)

    def test_flat_delivery_arc_is_rejected_then_rewritten(self) -> None:
        calls = 0

        def flat_then_varied(*, user_prompt, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                flat = json.loads(json.dumps(WALKING_JSON))
                for item in flat["blocks"]:
                    item["delivery"] = "settling"
                return json.dumps(flat)
            self.assertIn("delivery", user_prompt.lower())
            return json.dumps(WALKING_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=flat_then_varied)
        written = writer.write(PRACTICES["walking"], minutes=10, theme="the coast road")

        self.assertTrue(written.retried)
        self.assertEqual(calls, 2)
        self.assertTrue(any("delivery" in problem for problem in written.retry_problems))

    def test_five_minute_script_with_too_many_blocks_is_rewritten_before_voice(self) -> None:
        calls = 0

        def oversized_then_valid(*, user_prompt, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                oversized = json.loads(json.dumps(WALKING_JSON))
                ordinary = {
                    "text": "Keep walking and feel the ground beneath each step.",
                    "pause_seconds": 4.5,
                    "pause_instruction": None,
                    "delivery": "grounding",
                }
                oversized["blocks"][-1:-1] = [ordinary.copy() for _ in range(8)]
                return json.dumps(oversized)
            self.assertIn("fit 5 minutes", user_prompt.lower())
            return json.dumps(WALKING_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=oversized_then_valid)
        written = writer.write(PRACTICES["walking"], minutes=5)

        self.assertTrue(written.retried)
        self.assertEqual(calls, 2)
        self.assertTrue(any("fit 5 minutes" in problem for problem in written.retry_problems))

    def test_five_minute_script_with_excess_minimum_silence_is_rewritten(self) -> None:
        calls = 0

        def overpaused_then_valid(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                overpaused = json.loads(json.dumps(WALKING_JSON))
                practice = {
                    "text": "Keep walking and feel the ground.",
                    "pause_instruction": "Notice each step as it lands.",
                    "delivery": "spacious",
                }
                # Each practice pause now carries a fixed 25s minimum in code,
                # so many practice pauses blow the 5-minute budget.
                overpaused["blocks"][-1:-1] = [practice.copy() for _ in range(10)]
                return json.dumps(overpaused)
            return json.dumps(WALKING_JSON)

        writer = ScriptWriter(api_key="test-key", llm_call=overpaused_then_valid)
        written = writer.write(PRACTICES["walking"], minutes=5)

        self.assertTrue(written.retried)
        self.assertTrue(any("fit 5 minutes" in problem for problem in written.retry_problems))

    def test_write_picks_theme_from_bank_when_unspecified(self) -> None:
        writer = ScriptWriter(api_key="test-key", llm_call=fake_llm_call)
        written = writer.write(PRACTICES["walking"], minutes=10)
        self.assertIn(written.theme, PRACTICES["walking"].themes)

    def test_llm_chosen_pause_seconds_are_honoured_exactly(self) -> None:
        def pause_chosen_llm(*, user_prompt, **kwargs):
            payload = {
                "blocks": [
                    {"text": "Welcome.", "pause_instruction": None, "pause_seconds": None, "delivery": "settling"},
                    {"text": "Rest your body on the bed in the dark.", "pause_instruction": None, "pause_seconds": None, "delivery": "grounding"},
                    {
                        "text": "Let the body settle into the mattress.",
                        "pause_instruction": "Feel the weight of your legs, arms, and head.",
                        "pause_seconds": 40,
                        "delivery": "spacious",
                    },
                    {"text": "If attention wanders, return to the bed.", "pause_instruction": None, "pause_seconds": None, "delivery": "encouraging"},
                    {"text": "With your eyes closed, rest here for a while.", "pause_instruction": None, "pause_seconds": None, "delivery": "closing"},
                ]
            }
            return json.dumps(payload)

        writer = ScriptWriter(api_key="test-key", llm_call=pause_chosen_llm)
        written = writer.write(PRACTICES["sleep"], minutes=5, theme="the dark behind your closed eyes")

        self.assertFalse(written.retried)
        practice = [block for block in written.blocks if block.pause_instruction]
        self.assertEqual(len(practice), 1)
        self.assertAlmostEqual(practice[0].pause_min_seconds, 40.0, places=6)
        # Weight 0: the silence allocator must not inflate the LLM's choice.
        self.assertEqual(practice[0].pause_weight, 0.0)

    def test_long_pause_seconds_without_spoken_instruction_is_rejected(self) -> None:
        def bad_pause_llm(*, user_prompt, **kwargs):
            payload = {
                "blocks": [
                    {"text": "Welcome.", "pause_instruction": None, "pause_seconds": None, "delivery": "settling"},
                    {"text": "Rest your body on the bed.", "pause_instruction": None, "pause_seconds": 40, "delivery": "grounding"},
                    {"text": "The room is quiet around you.", "pause_instruction": None, "pause_seconds": None, "delivery": "closing"},
                ]
            }
            return json.dumps(payload)

        writer = ScriptWriter(api_key="test-key", llm_call=bad_pause_llm)
        with self.assertRaises(ValueError) as context:
            writer.write(PRACTICES["sleep"], minutes=5, theme="the dark behind your closed eyes")
        self.assertIn("without a spoken instruction", str(context.exception))

    def test_system_prompt_has_no_flat_read_rule(self) -> None:
        self.assertNotIn("read flat and even", _SYSTEM_PROMPT)
        self.assertNotIn("cannot add emphasis", _SYSTEM_PROMPT)
        self.assertNotIn("no need to strip tone out of the words", _SYSTEM_PROMPT)

    def test_system_prompt_tells_the_llm_to_choose_pause_placement_and_length(self) -> None:
        self.assertIn("You decide where the longer pauses go", _SYSTEM_PROMPT)
        self.assertIn("pause_seconds", _SYSTEM_PROMPT)
        self.assertIn("honours your value exactly", _SYSTEM_PROMPT)

    def test_system_prompt_forbids_brightening_for_sleep_and_softens_the_arc(self) -> None:
        self.assertIn('never use "brightening"', _SYSTEM_PROMPT)
        self.assertIn("no sudden lift in energy", _SYSTEM_PROMPT)
        self.assertIn("calm, soft, and soothing", _SYSTEM_PROMPT)

    def test_system_prompt_keeps_punctuation_inside_a_line(self) -> None:
        self.assertIn("where a pause naturally falls", _SYSTEM_PROMPT)

    def test_invalid_json_surfaces_problem(self) -> None:
        def bad_llm(*args, **kwargs):
            return "not json at all"

        writer = ScriptWriter(api_key="test-key", llm_call=bad_llm)
        with self.assertRaises(ValueError):
            writer.write(PRACTICES["breath_anchor"], minutes=10)

    def test_rule_violation_retries_then_raises(self) -> None:
        def violating_llm(*, user_prompt, **kwargs):
            payload = {
                "blocks": [
                    {"text": "Welcome.", "pause_instruction": None, "delivery": "settling"},
                    {"text": "Breathe in deeply and hold your breath.", "pause_instruction": None, "delivery": "grounding"},
                    {"text": "Notice the breath.", "pause_instruction": "Watch the breath.", "delivery": "spacious"},
                ]
            }
            return json.dumps(payload)

        writer = ScriptWriter(api_key="test-key", llm_call=violating_llm)
        with self.assertRaises(ValueError) as context:
            writer.write(PRACTICES["breath_anchor"], minutes=10, theme="the tide")
        self.assertIn("failed validation twice", str(context.exception))

    def test_sleep_script_using_brightening_is_rejected_then_rewritten(self) -> None:
        calls = 0

        def bright_then_valid(*, user_prompt, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                payload = {
                    "blocks": [
                        {"text": "Welcome.", "pause_instruction": None, "delivery": "settling"},
                        {"text": "Let the body settle into the bed.", "pause_instruction": None, "delivery": "grounding"},
                        {"text": "The room is dark and quiet around you.", "pause_instruction": None, "delivery": "spacious"},
                        {
                            "text": "Let the body rest into the mattress.",
                            "pause_instruction": "During this silence, feel the weight of the body.",
                            "delivery": "spacious",
                        },
                        {"text": "Feel a small lift in energy as you wake.", "pause_instruction": None, "delivery": "brightening"},
                        {"text": "Rest here a while longer.", "pause_instruction": None, "delivery": "closing"},
                    ]
                }
                return json.dumps(payload)
            self.assertIn("brightening", user_prompt)
            payload = {
                "blocks": [
                    {"text": "Welcome.", "pause_instruction": None, "delivery": "settling"},
                    {"text": "Let the body settle into the bed.", "pause_instruction": None, "delivery": "grounding"},
                    {"text": "The room is dark and quiet around you.", "pause_instruction": None, "delivery": "spacious"},
                    {
                        "text": "Let the body rest into the mattress.",
                        "pause_instruction": "During this silence, feel the weight of the body.",
                        "delivery": "spacious",
                    },
                    {"text": "If your attention moves, return gently to the bed.", "pause_instruction": None, "delivery": "encouraging"},
                    {"text": "Rest here a while longer.", "pause_instruction": None, "delivery": "closing"},
                ]
            }
            return json.dumps(payload)

        writer = ScriptWriter(api_key="test-key", llm_call=bright_then_valid)
        written = writer.write(PRACTICES["sleep"], minutes=5)

        self.assertTrue(written.retried)
        self.assertEqual(calls, 2)
        self.assertTrue(any("brightening" in problem for problem in written.retry_problems))

    def test_missing_api_key_raises(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            writer = ScriptWriter(api_key="", env_path=Path(temp) / "no-env")
            with self.assertRaises(RuntimeError):
                writer.write(PRACTICES["focus"], minutes=5)

    def test_boolean_pause_instruction_is_rejected(self) -> None:
        def boolean_instruction_llm(*, user_prompt, **kwargs):
            payload = {
                "blocks": [
                    {"text": "Welcome.", "pause_instruction": None, "delivery": "settling"},
                    {"text": "Notice the breath.", "pause_instruction": True, "delivery": "spacious"},
                ]
            }
            return json.dumps(payload)

        writer = ScriptWriter(api_key="test-key", llm_call=boolean_instruction_llm)
        with self.assertRaises(ValueError) as context:
            writer.write(PRACTICES["breath_anchor"], minutes=5, theme="the tide")
        self.assertIn("not a spoken string", str(context.exception))


if __name__ == "__main__":
    unittest.main()
