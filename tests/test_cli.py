import unittest

from meditation.cli import build_parser


class MeditationCliTests(unittest.TestCase):
    def test_course_uses_selected_paid_voice_by_default(self) -> None:
        args = build_parser().parse_args(["course", "--day", "1"])

        self.assertEqual(args.provider, "inworld-meditation")

    def test_one_off_requires_topic_and_accepts_situation(self) -> None:
        args = build_parser().parse_args(
            ["meditation", "--topic", "anxiety", "--situation", "before a meeting", "--minutes", "5"]
        )

        self.assertEqual(args.topic, "anxiety")
        self.assertEqual(args.situation, "before a meeting")
        self.assertEqual(args.minutes, 5)
        self.assertIsNone(args.practice)

    def test_one_off_accepts_an_explicit_practice(self) -> None:
        args = build_parser().parse_args(
            ["meditation", "--topic", "anxiety", "--practice", "body_scan", "--minutes", "5"]
        )

        self.assertEqual(args.topic, "anxiety")
        self.assertEqual(args.practice, "body_scan")

    def test_one_off_rejects_unknown_topic(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["meditation", "--topic", "not-a-topic"])


if __name__ == "__main__":
    unittest.main()