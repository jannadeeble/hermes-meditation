import unittest
from pathlib import Path

from meditation.curriculum import load_foundation_course


CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


class FoundationCourseTests(unittest.TestCase):
    def test_course_has_thirty_ordered_lessons_and_ready_lessons_are_written(self) -> None:
        course = load_foundation_course(CONTENT_ROOT)

        self.assertEqual([lesson.day for lesson in course.lessons], list(range(1, 31)))
        self.assertEqual([lesson.day for lesson in course.lessons if lesson.status == "ready"], [1, 16])

    def test_day_one_teaches_one_practice_with_one_evidence_card(self) -> None:
        course = load_foundation_course(CONTENT_ROOT)
        lesson = course.lesson(1)

        self.assertEqual(lesson.title, "Beginning again")
        self.assertEqual(lesson.practice, "breath_anchor")
        self.assertEqual(lesson.evidence_card_ids, ("attention-return-001",))
        self.assertGreaterEqual(len(lesson.script_blocks), 20)
        self.assertEqual(lesson.speech_tempo, 1.0)
        self.assertEqual(lesson.opening_silence_seconds, 5.0)
        self.assertIsNotNone(lesson.soundscape)
        self.assertTrue(all(block.text.strip() for block in lesson.script_blocks))
        self.assertTrue(
            all(
                block.pause_instruction
                for block in lesson.script_blocks
                if block.pause_weight > 0 or block.pause_min_seconds > 8
            )
        )
        self.assertEqual(lesson.script_blocks[0].text, "Welcome.")
        self.assertEqual(lesson.script_blocks[0].pause_min_seconds, 3.0)
        self.assertEqual(lesson.script_blocks[0].pause_weight, 0)
        ordinary_gaps = {
            block.pause_min_seconds
            for block in lesson.script_blocks[1:]
            if block.pause_weight == 0 and block.pause_min_seconds > 0
        }
        self.assertEqual(ordinary_gaps, {4.5})

    def test_day_one_gently_sets_up_the_body_eyes_and_session(self) -> None:
        lesson = load_foundation_course(CONTENT_ROOT).lesson(1)
        opening = " ".join(block.spoken_text.lower() for block in lesson.script_blocks[:10])

        self.assertIn("take your weight", opening)
        self.assertIn("close your eyes", opening)
        self.assertIn("slightly open", opening)
        self.assertIn("over the next few minutes", opening)
        self.assertIn("feeling of breathing", opening)

    def test_day_one_supports_selectable_session_lengths(self) -> None:
        lesson = load_foundation_course(CONTENT_ROOT).lesson(1)

        self.assertEqual(lesson.min_session_minutes, 5)
        self.assertEqual(lesson.max_session_minutes, 20)

        short = lesson.blocks_for_minutes(5)
        full = lesson.blocks_for_minutes(10)

        self.assertGreaterEqual(len(full), 20)
        self.assertLess(len(short), len(full))
        self.assertEqual(short[0].text, "Welcome.")
        self.assertTrue(
            all(block.pause_instruction for block in short if block.pause_weight > 0 or block.pause_min_seconds > 8)
        )
        spoken_short = " ".join(block.spoken_text.lower() for block in short)
        self.assertIn("choose one place", spoken_short)
        self.assertIn("each return is one small act of training", spoken_short)
        self.assertIn("during the day", spoken_short)
        self.assertNotIn("practise on your own", spoken_short)

    def test_session_below_lesson_minimum_is_rejected(self) -> None:
        lesson = load_foundation_course(CONTENT_ROOT).lesson(1)

        with self.assertRaisesRegex(ValueError, "at least 5"):
            lesson.blocks_for_minutes(3)

    def test_day_sixteen_is_a_ready_walking_lesson_with_walking_cues(self) -> None:
        course = load_foundation_course(CONTENT_ROOT)
        lesson = course.lesson(16)

        self.assertEqual(lesson.status, "ready")
        self.assertEqual(lesson.practice, "walking")
        self.assertEqual(lesson.title, "Walking with attention")
        self.assertEqual(lesson.evidence_card_ids, ("attention-return-001",))
        self.assertEqual(lesson.opening_silence_seconds, 5.0)
        self.assertIsNotNone(lesson.soundscape)
        self.assertGreaterEqual(len(lesson.script_blocks), 20)
        self.assertEqual(lesson.script_blocks[0].text, "Welcome.")
        spoken = " ".join(block.spoken_text.lower() for block in lesson.script_blocks)

        self.assertIn("walking", spoken)
        self.assertIn("step", spoken)
        self.assertIn("ground", spoken)
        for phrase in ("chair", "sit", "close your eyes", "floor beneath you"):
            self.assertNotIn(phrase, spoken)
        self.assertTrue(
            all(
                block.pause_instruction
                for block in lesson.script_blocks
                if block.pause_weight > 0 or block.pause_min_seconds > 8
            )
        )
        for phrase in ("first practice", "first lesson", "second lesson", "day one", "day sixteen"):
            self.assertNotIn(phrase, spoken)

    def test_spoken_script_does_not_name_course_position(self) -> None:
        lesson = load_foundation_course(CONTENT_ROOT).lesson(1)
        spoken = " ".join(block.spoken_text.lower() for block in lesson.script_blocks)

        for phrase in ("first practice", "first lesson", "second lesson", "day one", "day two"):
            self.assertNotIn(phrase, spoken)

    def test_unwritten_lesson_cannot_be_rendered(self) -> None:
        course = load_foundation_course(CONTENT_ROOT)

        with self.assertRaisesRegex(ValueError, "not ready"):
            course.renderable_lesson(2)


if __name__ == "__main__":
    unittest.main()
