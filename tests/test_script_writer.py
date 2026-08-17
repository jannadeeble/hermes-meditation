import unittest

from meditation.practices import PRACTICES, known_practice_keys, practice_spec
from meditation.validation import validate_script
from meditation.models import ScriptBlock


def block(text: str, pause_min: float = 4.5, weight: float = 0.0, instruction: str | None = None) -> ScriptBlock:
    return ScriptBlock(
        text=text,
        pause_min_seconds=pause_min,
        pause_weight=weight,
        pause_instruction=instruction,
        min_minutes=1,
    )


class PracticeCatalogTests(unittest.TestCase):
    def test_known_practice_keys_are_sorted_and_covered(self) -> None:
        keys = known_practice_keys()
        self.assertEqual(keys, tuple(sorted(PRACTICES)))
        self.assertIn("walking", keys)
        self.assertIn("breath_anchor", keys)
        self.assertIn("body_scan", keys)
        self.assertIn("loving_kindness", keys)
        self.assertIn("sleep", keys)
        self.assertIn("focus", keys)

    def test_every_practice_has_cues_forbidden_rules_and_themes(self) -> None:
        for key, spec in PRACTICES.items():
            with self.subTest(practice=key):
                self.assertTrue(spec.cue_vocabulary)
                self.assertTrue(spec.themes)
                self.assertTrue(spec.attention_target)
                self.assertTrue(spec.return_cue)
                self.assertNotEqual(spec.posture, "")
                self.assertEqual(practice_spec(key), spec)

    def test_unknown_practice_raises(self) -> None:
        with self.assertRaises(ValueError):
            practice_spec("not-a-practice")

    def test_pick_theme_prefers_requested(self) -> None:
        spec = PRACTICES["walking"]
        self.assertEqual(spec.pick_theme("the coast road"), "the coast road")
        self.assertIn(spec.pick_theme(), spec.themes)


class ValidationTests(unittest.TestCase):
    def test_walking_script_passes(self) -> None:
        spec = PRACTICES["walking"]
        blocks = (
            block("Welcome."),
            block("Find a pace that is your own."),
            block(
                "Let each step land softly.",
                pause_min=25,
                weight=1.0,
                instruction="When attention wanders, return to the ground under your feet.",
            ),
            block("During the day, one ordinary step can be enough."),
        )
        self.assertEqual(validate_script(blocks, spec), [])

    def test_walking_script_with_seated_cue_fails(self) -> None:
        spec = PRACTICES["walking"]
        blocks = (
            block("Welcome."),
            block("Sit comfortably and close your eyes."),
            block("Bring attention to your steps."),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("forbidden" in p and "sit" in p for p in problems))

    def test_breath_script_with_forced_breath_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("Breathe in deeply and hold your breath for a moment."),
            block("Notice the breath coming and going."),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("hold your breath" in p for p in problems))

    def test_long_pause_without_instruction_fails(self) -> None:
        # Construct a block with a long pause but no instruction by bypassing
        # __init__ (which already rejects this shape at build time).
        spec = PRACTICES["breath_anchor"]
        raw = object.__new__(ScriptBlock)
        object.__setattr__(raw, "text", "Notice the breath.")
        object.__setattr__(raw, "pause_min_seconds", 30)
        object.__setattr__(raw, "pause_weight", 1.0)
        object.__setattr__(raw, "pause_instruction", None)
        object.__setattr__(raw, "min_minutes", 1)
        blocks = (
            block("Welcome."),
            raw,
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("without a spoken instruction" in p for p in problems))

    def test_pause_instruction_that_repeats_the_block_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("Notice the natural breath coming and going."),
            block(
                "Follow the in breath and the out breath.",
                pause_min=25,
                weight=1.0,
                instruction="Follow the in breath and the out breath.",
            ),
        )

        problems = validate_script(blocks, spec)

        self.assertTrue(any("repeats" in problem for problem in problems))

    def test_near_duplicate_spoken_lines_fail(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("When attention wanders, return to the next natural breath."),
            block("When your attention wanders, return gently to the next natural breath."),
        )

        problems = validate_script(blocks, spec)

        self.assertTrue(any("near-duplicate" in problem for problem in problems))

    def test_course_position_wording_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("This is the first lesson of the course."),
            block("Notice the breath."),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("course-position" in p for p in problems))

    def test_missing_welcome_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (block("Notice the breath."),)
        problems = validate_script(blocks, spec)
        self.assertTrue(any("open with a short welcome" in p for p in problems))

    def test_welcome_merged_with_first_line_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome. Settle into your seat and let your shoulders drop."),
            block("Notice the breath."),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("own short line" in p for p in problems))

    def test_long_chunk_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block(
                "Notice the way the breath moves in and out of the body at its own natural pace, without you doing anything at all."
            ),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("too long for one spoken line" in p for p in problems))

    def test_woo_phrasing_fails(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("Align your energy and raise your vibration."),
            block("Notice the breath."),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("woo-woo" in p for p in problems))

    def test_conversational_script_passes(self) -> None:
        spec = PRACTICES["breath_anchor"]
        blocks = (
            block("Welcome."),
            block("Settle into your seat and let your shoulders drop."),
            block("Feel the air move in and out on its own."),
            block(
                "Keep following the next breath.",
                pause_min=25,
                weight=1.0,
                instruction="When your mind wanders, come back to the next breath.",
            ),
            block("For the rest of the day, one breath is enough to come back to."),
        )
        self.assertEqual(validate_script(blocks, spec), [])

    def test_sleep_script_using_brightening_fails(self) -> None:
        spec = PRACTICES["sleep"]
        blocks = (
            block("Welcome."),
            block("Let the body settle into the bed."),
            ScriptBlock("Return to the day.", 4.5, 0.0, delivery="brightening"),
        )
        problems = validate_script(blocks, spec)
        self.assertTrue(any("brightening" in p and "sleep" in p for p in problems))

    def test_sleep_script_returning_to_a_walking_anchor_fails(self) -> None:
        spec = PRACTICES["sleep"]
        blocks = (
            ScriptBlock("Welcome.", 4.5, 0.0, delivery="settling", stage="arrival"),
            ScriptBlock(
                "Let the body settle into the bed.",
                4.5,
                0.0,
                delivery="grounding",
                stage="teaching",
            ),
            ScriptBlock(
                "Rest into the mattress.",
                25.0,
                1.0,
                pause_instruction="Feel the weight of the body.",
                delivery="spacious",
                stage="practice",
            ),
            ScriptBlock(
                "Then return to the next step you can feel.",
                4.5,
                0.0,
                delivery="encouraging",
                stage="wandering_return",
            ),
        )
        problems = validate_script(blocks, spec, require_arc=True)
        self.assertTrue(
            any("walking" in p and "step" in p for p in problems),
            f"expected a wrong-return-cue problem, got: {problems}",
        )

    def test_sleep_script_paraphrasing_its_own_anchor_passes(self) -> None:
        spec = PRACTICES["sleep"]
        blocks = (
            ScriptBlock("Welcome.", 4.5, 0.0, delivery="settling", stage="arrival"),
            ScriptBlock(
                "Let the body settle into the bed.",
                4.5,
                0.0,
                delivery="grounding",
                stage="teaching",
            ),
            ScriptBlock(
                "The room is dark and quiet.",
                4.5,
                0.0,
                delivery="grounding",
                stage="teaching",
            ),
            ScriptBlock(
                "Let the body rest into the mattress.",
                25.0,
                1.0,
                pause_instruction="During this silence, feel the weight of the body.",
                delivery="spacious",
                stage="practice",
            ),
            ScriptBlock(
                "When attention moves, settle back into the warmth of the bed.",
                4.5,
                0.0,
                delivery="encouraging",
                stage="wandering_return",
            ),
            ScriptBlock(
                "Let the body rest a while longer, with less guidance.",
                25.0,
                1.0,
                pause_instruction="For this silence, keep resting.",
                delivery="spacious",
                stage="deepening",
            ),
            ScriptBlock(
                "Rest is enough, and the day is done.",
                4.5,
                0.0,
                delivery="closing",
                stage="integration",
            ),
            ScriptBlock(
                "Let the eyes stay soft and the body heavy.",
                4.5,
                0.0,
                delivery="closing",
                stage="closing",
            ),
        )
        self.assertEqual(validate_script(blocks, spec, require_arc=True), [])

    def test_teaching_stage_missing_fails_when_arc_required(self) -> None:
        spec = PRACTICES["sleep"]
        blocks = (
            ScriptBlock("Welcome.", 4.5, 0.0, delivery="settling", stage="arrival"),
            ScriptBlock(
                "Let the body settle into the bed.",
                4.5,
                0.0,
                delivery="grounding",
                stage="practice",
            ),
        )
        problems = validate_script(blocks, spec, require_arc=True)
        self.assertTrue(any("teaching stage" in p for p in problems))

    def test_teaching_stage_without_spoken_text_fails(self) -> None:
        spec = PRACTICES["sleep"]
        # Bypass __init__ (which rejects empty text at build time) to prove
        # the validator catches an empty teaching stage on its own.
        raw = object.__new__(ScriptBlock)
        object.__setattr__(raw, "text", "   ")
        object.__setattr__(raw, "pause_min_seconds", 4.5)
        object.__setattr__(raw, "pause_weight", 0.0)
        object.__setattr__(raw, "pause_instruction", None)
        object.__setattr__(raw, "min_minutes", 1)
        object.__setattr__(raw, "delivery", "grounding")
        object.__setattr__(raw, "stage", "teaching")
        blocks = (
            ScriptBlock("Welcome.", 4.5, 0.0, delivery="settling", stage="arrival"),
            raw,
        )
        problems = validate_script(blocks, spec, require_arc=True)
        self.assertTrue(any("no spoken text" in p for p in problems))

    def test_light_topic_checks_do_not_run_without_required_arc(self) -> None:
        spec = PRACTICES["sleep"]
        blocks = (
            block("Welcome."),
            block("Let the body settle into the bed."),
        )
        self.assertEqual(validate_script(blocks, spec), [])


if __name__ == "__main__":
    unittest.main()
