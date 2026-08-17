import unittest

from meditation.models import ScriptBlock
from meditation.score import allocate_silence


class ScoreTests(unittest.TestCase):
    def test_extra_silence_only_extends_instructed_practice_pauses(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", pause_min_seconds=2.0, pause_weight=0.0),
            ScriptBlock(
                "Bring attention to the breath.",
                pause_min_seconds=5.0,
                pause_weight=1.0,
                pause_instruction="For the next few moments, follow each breath.",
            ),
        )

        pauses = allocate_silence(blocks, speech_seconds=4.0, target_seconds=14.0)

        self.assertAlmostEqual(sum(pauses) + 4.0, 14.0, places=6)
        self.assertAlmostEqual(pauses[0], 2.0, places=6)
        self.assertAlmostEqual(pauses[1], 8.0, places=6)

    def test_long_or_weighted_pause_requires_a_spoken_instruction(self) -> None:
        with self.assertRaisesRegex(ValueError, "instruction"):
            ScriptBlock("Welcome.", pause_min_seconds=10.0, pause_weight=0.0)
        with self.assertRaisesRegex(ValueError, "instruction"):
            ScriptBlock("A teaching.", pause_min_seconds=2.0, pause_weight=1.0)

    def test_llm_chosen_pause_seconds_are_honoured_and_leftover_becomes_tail(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", pause_min_seconds=1.5, pause_weight=0.0),
            ScriptBlock(
                "Now rest on the bed.",
                pause_min_seconds=30.0,
                pause_weight=0.0,
                pause_instruction="Feel the weight of your body.",
            ),
        )

        pauses = allocate_silence(blocks, speech_seconds=8.0, target_seconds=60.0)

        self.assertAlmostEqual(pauses[0], 1.5, places=6)
        self.assertAlmostEqual(pauses[1], 30.0, places=6)
        # The LLM chose exact pause lengths; spare time is left as trailing quiet.
        self.assertLess(sum(pauses) + 8.0, 60.0)

    def test_silence_allocation_rejects_overlong_speech(self) -> None:
        blocks = (
            ScriptBlock(
                "one",
                pause_min_seconds=2.0,
                pause_weight=1.0,
                pause_instruction="Keep feeling the breath.",
            ),
        )

        with self.assertRaisesRegex(ValueError, "too long"):
            allocate_silence(blocks, speech_seconds=9.0, target_seconds=10.0)


if __name__ == "__main__":
    unittest.main()
