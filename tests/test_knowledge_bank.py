import unittest
from pathlib import Path

from meditation.knowledge_bank import (
    auto_pick_practice,
    load_knowledge_bank,
    select_topic_brief,
)
from meditation.practices import PRACTICES

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


class KnowledgeBankTests(unittest.TestCase):
    def test_load_knowledge_bank_reads_all_topics_and_points(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        self.assertEqual(
            [topic.id for topic in bank.topics],
            ["anxiety", "stress", "sleep", "anger", "self-compassion", "focus", "relationships", "grief"],
        )
        for topic in bank.topics:
            with self.subTest(topic=topic.id):
                self.assertTrue(topic.name)
                self.assertTrue(topic.safety_notes)
                self.assertTrue(topic.points)
                for point in topic.points:
                    self.assertTrue(point.point)
                    self.assertTrue(point.explanation)
                    self.assertTrue(point.fit_practices)

    def test_select_topic_brief_uses_exact_practice_return_cue(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        brief = select_topic_brief(
            bank,
            topic_id="anxiety",
            spec=PRACTICES["breath_anchor"],
            minutes=5,
        )

        self.assertEqual(brief.topic_id, "anxiety")
        self.assertEqual(brief.return_cue, PRACTICES["breath_anchor"].return_cue)
        self.assertTrue(brief.points)
        self.assertTrue(
            all(
                PRACTICES["breath_anchor"].key in point.fit_practices
                for point in brief.points
            )
        )

    def test_select_topic_brief_scales_point_count_with_session_length(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        five = select_topic_brief(
            bank, topic_id="sleep", spec=PRACTICES["sleep"], minutes=5
        )
        ten = select_topic_brief(
            bank, topic_id="sleep", spec=PRACTICES["sleep"], minutes=10
        )
        twenty = select_topic_brief(
            bank, topic_id="sleep", spec=PRACTICES["sleep"], minutes=20
        )

        self.assertEqual(len(five.points), 1)
        self.assertEqual(len(ten.points), 2)
        self.assertEqual(len(twenty.points), 3)

    def test_select_topic_brief_avoids_recent_points_when_others_exist(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        brief = select_topic_brief(
            bank,
            topic_id="anxiety",
            spec=PRACTICES["breath_anchor"],
            minutes=5,
            recent_point_ids=("A1",),
        )

        # A2-A5 also fit breath_anchor, so the recent A1 is skipped.
        self.assertEqual(len(brief.points), 1)
        self.assertNotEqual(brief.points[0].id, "A1")

    def test_select_topic_brief_rejects_practice_that_fits_no_point(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        with self.assertRaisesRegex(ValueError, "no teaching points"):
            select_topic_brief(
                bank,
                topic_id="anxiety",
                spec=PRACTICES["walking"],
                minutes=5,
            )

    def test_auto_pick_practice_returns_first_engine_practice_the_topic_fits(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        self.assertEqual(auto_pick_practice(bank, "anxiety"), "breath_anchor")
        self.assertEqual(auto_pick_practice(bank, "self-compassion"), "breath_anchor")

    def test_auto_pick_practice_nudges_sleep_for_bed_night_lying(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        self.assertEqual(
            auto_pick_practice(bank, "anxiety", situation="lying in bed worrying about tomorrow"),
            "sleep",
        )
        self.assertEqual(
            auto_pick_practice(bank, "anxiety", situation="worrying at night"),
            "sleep",
        )

    def test_auto_pick_practice_nudges_walking_for_walk_outdoors(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        self.assertEqual(
            auto_pick_practice(bank, "stress", situation="out on a walk"),
            "walking",
        )

    def test_auto_pick_practice_nudges_kindness_for_social_but_falls_back_to_breath(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        # Anxiety does not fit loving_kindness, so a social situation falls
        # back to the topic's fitting default.
        self.assertEqual(
            auto_pick_practice(bank, "anxiety", situation="a social event tonight"),
            "breath_anchor",
        )
        self.assertEqual(
            auto_pick_practice(bank, "self-compassion", situation="about to see people"),
            "loving_kindness",
        )

    def test_auto_pick_practice_empty_situation_keeps_topic_default(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        self.assertEqual(auto_pick_practice(bank, "anxiety", situation=""), "breath_anchor")

    def test_auto_pick_practice_uses_llm_judge_when_available(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        def judge(*, user_prompt, **kwargs):
            self.assertIn("lethargic", user_prompt)
            self.assertIn("breath_anchor", user_prompt)  # allowed practices listed
            return '{"practice": "breath_anchor"}'

        # self-compassion fits breath_anchor and loving_kindness. The LLM
        # picks breath_anchor for lethargy; the deterministic nudge would
        # have chosen loving_kindness because the situation says "event",
        # so a breath_anchor result proves the LLM judge was honored.
        self.assertEqual(
            auto_pick_practice(
                bank,
                "self-compassion",
                situation="lethargic before a family event",
                llm_call=judge,
                api_key="test",
                base_url="http://test",
                model="test",
            ),
            "breath_anchor",
        )

    def test_auto_pick_practice_falls_back_when_llm_returns_invalid(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        def judge(*, user_prompt, **kwargs):
            return '{"practice": "not_a_real_practice"}'

        # Invalid choice falls back to the deterministic nudge; the
        # situation says "event", which nudges toward loving_kindness.
        self.assertEqual(
            auto_pick_practice(
                bank,
                "self-compassion",
                situation="lethargic before a family event",
                llm_call=judge,
                api_key="test",
                base_url="http://test",
                model="test",
            ),
            "loving_kindness",
        )

    def test_auto_pick_practice_falls_back_when_llm_raises(self) -> None:
        bank = load_knowledge_bank(CONTENT_ROOT)

        def judge(*, user_prompt, **kwargs):
            raise RuntimeError("api down")

        # stress fits walking; the nudge sees "walk" and picks it even when
        # the LLM call fails.
        self.assertEqual(
            auto_pick_practice(
                bank,
                "stress",
                situation="out on a walk",
                llm_call=judge,
                api_key="test",
                base_url="http://test",
                model="test",
            ),
            "walking",
        )


if __name__ == "__main__":
    unittest.main()
