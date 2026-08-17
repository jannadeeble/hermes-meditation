import json
import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from meditation.curriculum import load_foundation_course
from meditation.models import ScriptBlock
from meditation.practices import PRACTICES
from meditation.publisher import PublishedFile
from meditation.script_writer import WrittenScript
from meditation.service import generate_foundation_session, generate_one_off_session
from meditation.storage import SessionStore


class FakeVoice:
    provider_name = "fake"

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        delivery: str = "grounding",
        practice: str | None = None,
    ) -> Path:
        rate = 24_000
        seconds = 0.3
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            for index in range(round(rate * seconds)):
                sample = int(500 * math.sin(2 * math.pi * 220 * index / rate))
                wav.writeframesraw(struct.pack("<h", sample))
        return output_path


class FakePublisher:
    def publish(self, file_path: Path, display_name: str) -> PublishedFile:
        return PublishedFile(
            viewer_url=f"https://files.example.com/token/{display_name}",
            raw_url=f"https://files.example.com/raw/token/{display_name}",
        )


class CapturingWriter:
    def __init__(self, blocks: tuple[ScriptBlock, ...]) -> None:
        self.blocks = blocks
        self.teaching = None
        self.topic = None

    def write(self, spec, *, minutes, theme=None, teaching=None, topic=None):
        self.teaching = teaching
        self.topic = topic
        return WrittenScript(
            blocks=self.blocks,
            theme=theme or "a quiet room",
            retried=False,
        )


def make_soundscape_root(tmp: Path, content_root: Path, seconds: float = 700.0) -> Path:
    lesson = load_foundation_course(content_root).lesson(1)
    assert lesson.soundscape
    target = tmp / lesson.soundscape
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=330:duration={seconds}",
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp


class MeditationServiceTests(unittest.TestCase):
    def test_course_writer_receives_the_day_objective_and_reviewed_teaching(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        lesson = load_foundation_course(content_root).lesson(1)
        writer = CapturingWriter(lesson.blocks_for_minutes(5))
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            soundscape_root = make_soundscape_root(temp_path, content_root)

            generate_foundation_session(
                day=1,
                minutes=5,
                content_root=content_root,
                store=SessionStore(temp_path / "sessions"),
                voice=FakeVoice(),
                publisher=FakePublisher(),
                session_id="course-teaching-handoff",
                soundscape_root=soundscape_root,
                writer=writer,
            )

        self.assertIsNotNone(writer.teaching)
        self.assertEqual(writer.teaching.teaching_point, lesson.objective)
        self.assertIn("Each return is one small act of training", writer.teaching.explanation)
        self.assertIn("next breath", writer.teaching.return_cue)

    def test_one_off_writer_uses_topic_brief_avoids_recent_points_and_records_its_choice(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0, delivery="settling", stage="arrival"),
            ScriptBlock("Notice the natural breath.", 4.5, 0, delivery="grounding", stage="teaching"),
            ScriptBlock(
                "Let attention settle on breathing.",
                25,
                1,
                pause_instruction="During this silence, feel each breath from beginning to end.",
                delivery="spacious",
                stage="practice",
            ),
            ScriptBlock(
                "Carry this attention into the day.",
                4.5,
                0,
                delivery="closing",
                stage="closing",
            ),
        )
        writer = CapturingWriter(blocks)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            store = SessionStore(temp_path / "sessions")
            store.create_session(
                "recent-session",
                {
                    "created_at": "2026-08-07T12:00:00+00:00",
                    "point_ids": ["A1"],
                },
            )

            generate_one_off_session(
                topic="anxiety",
                practice="breath_anchor",
                minutes=5,
                situation="before a meeting",
                content_root=content_root,
                store=store,
                voice=FakeVoice(),
                publisher=FakePublisher(),
                writer=writer,
                theme="a quiet room",
                session_id="one-off-topic-handoff",
                soundscape=None,
            )
            manifest = json.loads(
                (
                    temp_path
                    / "sessions"
                    / "one-off-topic-handoff"
                    / "manifest.json"
                ).read_text()
            )
            score = json.loads(
                (
                    temp_path
                    / "sessions"
                    / "one-off-topic-handoff"
                    / "score.json"
                ).read_text()
            )

        self.assertIsNotNone(writer.topic)
        self.assertIsNone(writer.teaching)
        self.assertEqual(writer.topic.topic_id, "anxiety")
        self.assertEqual(writer.topic.topic_name, "Anxiety")
        self.assertEqual(writer.topic.situation, "before a meeting")
        self.assertNotIn("A1", [point.id for point in writer.topic.points])
        self.assertIn("next breath", writer.topic.return_cue)
        self.assertEqual(manifest["topic_id"], "anxiety")
        self.assertEqual(manifest["topic_name"], "Anxiety")
        self.assertEqual(manifest["point_ids"], [point.id for point in writer.topic.points])
        self.assertEqual(manifest["situation"], "before a meeting")
        self.assertEqual(score["topic_id"], "anxiety")
        self.assertEqual(score["point_ids"], [point.id for point in writer.topic.points])
        self.assertEqual(
            [block["stage"] for block in score["blocks"]],
            ["arrival", "teaching", "practice", "closing"],
        )

    def test_one_off_auto_picks_practice_that_fits_the_topic(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0, delivery="settling", stage="arrival"),
            ScriptBlock("Settle into the bed.", 4.5, 0, delivery="grounding", stage="teaching"),
            ScriptBlock(
                "Let the body rest into the mattress.",
                25,
                1,
                pause_instruction="During this silence, feel the weight of the body.",
                delivery="spacious",
                stage="practice",
            ),
            ScriptBlock(
                "Rest here for a while.",
                4.5,
                0,
                delivery="closing",
                stage="closing",
            ),
        )
        writer = CapturingWriter(blocks)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)

            generate_one_off_session(
                topic="sleep",
                minutes=5,
                content_root=content_root,
                store=SessionStore(temp_path / "sessions"),
                voice=FakeVoice(),
                publisher=FakePublisher(),
                writer=writer,
                session_id="one-off-auto-practice",
                soundscape=None,
            )
            manifest = json.loads(
                (
                    temp_path
                    / "sessions"
                    / "one-off-auto-practice"
                    / "manifest.json"
                ).read_text()
            )

        self.assertEqual(manifest["practice"], "sleep")
        self.assertEqual(writer.topic.topic_id, "sleep")
        self.assertEqual(writer.topic.return_cue, PRACTICES["sleep"].return_cue)

    def test_day_one_generation_writes_audio_score_manifest_and_published_link(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            soundscape_root = make_soundscape_root(temp_path, content_root)
            store = SessionStore(temp_path / "sessions")
            result = generate_foundation_session(
                day=1,
                minutes=10,
                content_root=content_root,
                store=store,
                voice=FakeVoice(),
                publisher=FakePublisher(),
                session_id="test-day-one",
                soundscape_root=soundscape_root,
            )
            session_dir = temp_path / "sessions" / "test-day-one"
            manifest = json.loads((session_dir / "manifest.json").read_text())
            score = json.loads((session_dir / "score.json").read_text())

            self.assertTrue((session_dir / "meditation.wav").exists())
            self.assertTrue((session_dir / "meditation.mp3").exists())
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(manifest["voice_provider"], "fake")
            self.assertEqual(manifest["published_url"], result.published.viewer_url)
            self.assertEqual(score["target_seconds"], 600)
            self.assertEqual(score["opening_silence_seconds"], 5.0)
            self.assertGreaterEqual(len(score["blocks"]), 20)
            self.assertEqual(score["speech_tempo"], 1.0)
            self.assertIsNotNone(manifest["soundscape"])
            self.assertIsInstance(score["soundscape_start_seconds"], float)
            self.assertIsNotNone(score["soundscape_volume"])
            self.assertTrue(
                all(
                    block["pause_instruction"]
                    for block in score["blocks"]
                    if block["pause_weight"] > 0 or block["pause_min_seconds"] > 8
                )
            )
            self.assertTrue(all("delivery" in block for block in score["blocks"]))

    def test_five_minute_session_generates_exact_length_with_trimmed_script(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            soundscape_root = make_soundscape_root(temp_path, content_root)
            store = SessionStore(temp_path / "sessions")
            result = generate_foundation_session(
                day=1,
                minutes=5,
                content_root=content_root,
                store=store,
                voice=FakeVoice(),
                publisher=FakePublisher(),
                session_id="test-day-one-five",
                soundscape_root=soundscape_root,
            )
            session_dir = temp_path / "sessions" / "test-day-one-five"
            score = json.loads((session_dir / "score.json").read_text())
            manifest = json.loads((session_dir / "manifest.json").read_text())

            self.assertEqual(manifest["minutes"], 5)
            self.assertEqual(score["target_seconds"], 300)
            self.assertLess(len(score["blocks"]), 25)
            self.assertEqual(score["blocks"][0]["text"], "Welcome.")
            self.assertTrue(all(block["min_minutes"] <= 5 for block in score["blocks"]))

    def test_session_length_outside_lesson_range_is_rejected(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "at least 5"):
                generate_foundation_session(
                    day=1,
                    minutes=3,
                    content_root=content_root,
                    store=SessionStore(Path(temp) / "sessions"),
                    voice=FakeVoice(),
                    publisher=FakePublisher(),
                    session_id="test-too-short",
                )
            with self.assertRaisesRegex(ValueError, "at most 20"):
                generate_foundation_session(
                    day=1,
                    minutes=30,
                    content_root=content_root,
                    store=SessionStore(Path(temp) / "sessions"),
                    voice=FakeVoice(),
                    publisher=FakePublisher(),
                    session_id="test-too-long",
                )

    def test_unwritten_day_cannot_generate(self) -> None:
        content_root = Path(__file__).resolve().parents[1] / "content"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "not ready"):
                generate_foundation_session(
                    day=2,
                    minutes=1,
                    content_root=content_root,
                    store=SessionStore(Path(temp) / "sessions"),
                    voice=FakeVoice(),
                    publisher=FakePublisher(),
                    session_id="test-day-two",
                )


if __name__ == "__main__":
    unittest.main()
