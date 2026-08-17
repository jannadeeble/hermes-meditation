import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from meditation.models import ScriptBlock
from meditation.renderer import MeditationRenderer


class FakeTTS:
    def __init__(self, seconds_per_block: float) -> None:
        self.seconds_per_block = seconds_per_block
        self.texts: list[str] = []
        self.deliveries: list[str] = []
        self.practices: list[str | None] = []

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        delivery: str = "grounding",
        practice: str | None = None,
    ) -> Path:
        self.texts.append(text)
        self.deliveries.append(delivery)
        self.practices.append(practice)
        rate = 24_000
        frames = round(rate * self.seconds_per_block)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            for index in range(frames):
                sample = int(500 * math.sin(2 * math.pi * 220 * index / rate))
                wav.writeframesraw(struct.pack("<h", sample))
        return output_path


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def make_soundscape(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
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
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def rms(path: Path, start: float, seconds: float) -> float:
    rate = 24_000
    with wave.open(str(path), "rb") as wav:
        wav.setpos(round(start * rate))
        frames = wav.readframes(round(seconds * rate))
    if not frames:
        return 0.0
    values = [
        int.from_bytes(frames[i : i + 2], "little", signed=True)
        for i in range(0, len(frames), 2)
    ]
    return (sum(v * v for v in values) / len(values)) ** 0.5


class RendererTests(unittest.TestCase):
    def test_renderer_produces_exact_length_wav_and_mp3(self) -> None:
        blocks = (
            ScriptBlock("Settle into a comfortable position.", 1.5, 0.0, delivery="settling"),
            ScriptBlock(
                "Bring attention to the breath.",
                2.0,
                1.0,
                pause_instruction="Follow the next few breaths.",
                delivery="spacious",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            voice = FakeTTS(seconds_per_block=1.0)
            renderer = MeditationRenderer(voice, speech_tempo=0.9)
            result = renderer.render(
                blocks,
                opening_silence_seconds=3.0,
                target_seconds=12.0,
                output_dir=Path(temp),
            )

            self.assertTrue(result.wav_path.exists())
            self.assertTrue(result.mp3_path.exists())
            self.assertAlmostEqual(duration(result.wav_path), 12.0, delta=0.05)
            self.assertAlmostEqual(duration(result.mp3_path), 12.0, delta=0.1)
            self.assertAlmostEqual(
                result.opening_silence_seconds + sum(result.pause_seconds) + sum(result.speech_seconds),
                12.0,
                delta=0.05,
            )
            self.assertTrue(all(seconds > 1.05 for seconds in result.speech_seconds))
            self.assertAlmostEqual(result.pause_seconds[0], 1.5, delta=0.05)
            self.assertEqual(voice.deliveries, ["settling", "spacious"])
            with wave.open(str(result.wav_path), "rb") as wav:
                opening_frames = wav.readframes(round(wav.getframerate() * 3.0))
                first_spoken_frames = wav.readframes(round(wav.getframerate() * 0.5))
            self.assertEqual(set(opening_frames), {0})
            self.assertNotEqual(set(first_spoken_frames), {0})

    def test_renderer_forwards_the_practice_to_the_voice(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0.0, delivery="settling"),
            ScriptBlock(
                "Let the body rest into the bed.",
                2.0,
                1.0,
                pause_instruction="Feel the weight of the body.",
                delivery="spacious",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            voice = FakeTTS(seconds_per_block=1.0)
            renderer = MeditationRenderer(voice, practice="sleep")
            renderer.render(
                blocks,
                opening_silence_seconds=0.0,
                target_seconds=12.0,
                output_dir=Path(temp),
            )

            self.assertEqual(voice.practices, ["sleep", "sleep"])

    def test_renderer_sends_each_complete_line_to_the_voice(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0.0),
            ScriptBlock(
                "Soften your hands, your shoulders, and your face.",
                4.5,
                0.0,
                pause_instruction="Let each part rest against the bed.",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            voice = FakeTTS(seconds_per_block=1.0)
            renderer = MeditationRenderer(voice)
            result = renderer.render(
                blocks,
                opening_silence_seconds=0.0,
                target_seconds=16.0,
                output_dir=Path(temp),
            )

            self.assertEqual(
                voice.texts,
                [
                    "Welcome.",
                    (
                        "Soften your hands, your shoulders, and your face. "
                        "Let each part rest against the bed."
                    ),
                ],
            )
            self.assertEqual(len(voice.deliveries), 2)
            self.assertAlmostEqual(result.speech_seconds[1], 1.0, delta=0.05)
            self.assertAlmostEqual(duration(result.wav_path), 16.0, delta=0.05)

    def test_renderer_rejects_speech_that_cannot_fit(self) -> None:
        blocks = (
            ScriptBlock(
                "A long instruction.",
                2.0,
                1.0,
                pause_instruction="Keep practising.",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            renderer = MeditationRenderer(FakeTTS(seconds_per_block=9.0))

            with self.assertRaisesRegex(ValueError, "too long"):
                renderer.render(blocks, target_seconds=10.0, output_dir=Path(temp))

    def test_renderer_mixes_soundscape_under_voice_with_fades(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0.0),
            ScriptBlock(
                "Bring attention to the breath.",
                2.0,
                1.0,
                pause_instruction="Follow the next few breaths.",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            soundscape = make_soundscape(Path(temp) / "bed.mp3", seconds=30.0)
            renderer = MeditationRenderer(FakeTTS(seconds_per_block=1.0))
            result = renderer.render(
                blocks,
                opening_silence_seconds=5.0,
                target_seconds=12.0,
                output_dir=Path(temp) / "session",
                soundscape=soundscape,
                soundscape_start_seconds=2.0,
            )

            self.assertAlmostEqual(duration(result.wav_path), 12.0, delta=0.05)
            self.assertEqual(result.soundscape_start_seconds, 2.0)
            self.assertIsNotNone(result.soundscape_volume)
            # The soundscape fades in during the opening silence, so early audio is present.
            early_rms = rms(result.wav_path, start=1.0, seconds=1.0)
            self.assertGreater(early_rms, 50.0)
            # The soundscape is at full level by the middle, well above the fade-in.
            middle_rms = rms(result.wav_path, start=6.0, seconds=1.0)
            self.assertGreater(middle_rms, early_rms * 2.0)
            # The fade-out ends near silence at the very end.
            tail_rms = rms(result.wav_path, start=11.5, seconds=0.4)
            self.assertLess(tail_rms, early_rms)

    def test_renderer_rejects_soundscape_shorter_than_session(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0.0),
            ScriptBlock(
                "Bring attention to the breath.",
                2.0,
                1.0,
                pause_instruction="Follow the next few breaths.",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            soundscape = make_soundscape(Path(temp) / "bed.mp3", seconds=8.0)
            renderer = MeditationRenderer(FakeTTS(seconds_per_block=1.0))

            with self.assertRaisesRegex(ValueError, "too short"):
                renderer.render(
                    blocks,
                    opening_silence_seconds=5.0,
                    target_seconds=12.0,
                    output_dir=Path(temp) / "session",
                    soundscape=soundscape,
                )

    def test_renderer_rejects_soundscape_start_outside_file(self) -> None:
        blocks = (
            ScriptBlock("Welcome.", 1.5, 0.0),
            ScriptBlock(
                "Bring attention to the breath.",
                2.0,
                1.0,
                pause_instruction="Follow the next few breaths.",
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            soundscape = make_soundscape(Path(temp) / "bed.mp3", seconds=30.0)
            renderer = MeditationRenderer(FakeTTS(seconds_per_block=1.0))

            with self.assertRaisesRegex(ValueError, "outside"):
                renderer.render(
                    blocks,
                    opening_silence_seconds=5.0,
                    target_seconds=12.0,
                    output_dir=Path(temp) / "session",
                    soundscape=soundscape,
                    soundscape_start_seconds=25.0,
                )


if __name__ == "__main__":
    unittest.main()
