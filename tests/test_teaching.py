import unittest
from pathlib import Path

from meditation.curriculum import load_foundation_course
from meditation.practices import PRACTICES
from meditation.teaching import (
    TeachingCard,
    course_teaching_brief,
    load_teaching_cards,
    select_teaching_card,
)


CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


class TeachingCardTests(unittest.TestCase):
    def test_every_practice_has_more_than_one_teaching_choice(self) -> None:
        cards = load_teaching_cards(CONTENT_ROOT)

        for practice_key in PRACTICES:
            with self.subTest(practice=practice_key):
                matching = [
                    card for card in cards if practice_key in card.practice_keys
                ]
                self.assertGreaterEqual(len(matching), 2)

    def test_recent_teaching_card_is_avoided_when_another_choice_exists(self) -> None:
        first = TeachingCard(
            id="first",
            title="First",
            teaching_point="First point.",
            explanation="First explanation.",
            practice_keys=("breath_anchor",),
            daily_life_application="Use one breath before replying.",
        )
        second = TeachingCard(
            id="second",
            title="Second",
            teaching_point="Second point.",
            explanation="Second explanation.",
            practice_keys=("breath_anchor",),
            daily_life_application="Use one breath before replying.",
        )

        selected = select_teaching_card(
            (first, second),
            practice_key="breath_anchor",
            recent_ids=("first",),
        )

        self.assertEqual(selected.id, "second")

    def test_course_brief_carries_the_lesson_objective_and_reviewed_explanation(self) -> None:
        lesson = load_foundation_course(CONTENT_ROOT).lesson(1)

        brief = course_teaching_brief(
            CONTENT_ROOT,
            lesson,
            PRACTICES["breath_anchor"],
        )

        self.assertEqual(brief.id, "foundation-30-day-01")
        self.assertEqual(brief.title, lesson.title)
        self.assertEqual(brief.teaching_point, lesson.objective)
        self.assertIn("Each return is one small act of training", brief.explanation)
        self.assertIn("next breath", brief.return_cue)


if __name__ == "__main__":
    unittest.main()
