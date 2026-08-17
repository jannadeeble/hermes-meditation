import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meditation.storage import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_store_uses_current_hermes_home(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with patch.dict(os.environ, {"HERMES_HOME": first}):
                first_store = SessionStore.from_environment()
                first_path = first_store.create_session("session-one", {"day": 1})
            with patch.dict(os.environ, {"HERMES_HOME": second}):
                second_store = SessionStore.from_environment()
                second_path = second_store.create_session("session-two", {"day": 1})

            self.assertTrue(first_path.is_relative_to(Path(first)))
            self.assertTrue(second_path.is_relative_to(Path(second)))
            self.assertNotEqual(first_path.parent.parent, second_path.parent.parent)
            self.assertEqual(json.loads((first_path / "manifest.json").read_text()), {"day": 1})

    def test_session_identifier_cannot_escape_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HERMES_HOME": home}):
            store = SessionStore.from_environment()

            with self.assertRaisesRegex(ValueError, "session identifier"):
                store.create_session("../escape", {})

    def test_recent_teaching_cards_are_returned_newest_first_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(Path(temp) / "sessions")
            store.create_session(
                "session-one",
                {
                    "created_at": "2026-08-07T10:00:00+00:00",
                    "teaching_card_id": "attention-return",
                },
            )
            store.create_session(
                "session-two",
                {
                    "created_at": "2026-08-07T11:00:00+00:00",
                    "teaching_card_id": "effort-and-ease",
                },
            )
            store.create_session(
                "session-three",
                {
                    "created_at": "2026-08-07T12:00:00+00:00",
                    "teaching_card_id": "attention-return",
                },
            )

            recent = store.recent_teaching_card_ids(limit=2)

            self.assertEqual(recent, ("attention-return", "effort-and-ease"))

    def test_recent_topic_points_are_returned_newest_first_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(Path(temp) / "sessions")
            store.create_session(
                "session-one",
                {
                    "created_at": "2026-08-07T10:00:00+00:00",
                    "point_ids": ["A1", "A2"],
                },
            )
            store.create_session(
                "session-two",
                {
                    "created_at": "2026-08-07T11:00:00+00:00",
                    "point_ids": ["A3"],
                },
            )
            store.create_session(
                "session-three",
                {
                    "created_at": "2026-08-07T12:00:00+00:00",
                    "point_ids": ["A1"],
                },
            )

            recent = store.recent_topic_point_ids(limit=3)

            self.assertEqual(recent, ("A1", "A3", "A2"))


if __name__ == "__main__":
    unittest.main()
