import subprocess
import tempfile
import unittest
from pathlib import Path

from meditation.publisher import FilePublisher, LocalOnlyPublisher


class FilePublisherTests(unittest.TestCase):
    def test_publisher_returns_viewer_and_raw_urls(self) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                "https://files.example.com/token/foundation-day-01.mp3\n",
                "",
            )

        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "meditation.mp3"
            audio.write_bytes(b"audio")
            result = FilePublisher(
                script_path=Path("/fake/publish.sh"),
                url_prefix="https://files.example.com/",
                runner=runner,
            ).publish(audio, "foundation-day-01.mp3")

        self.assertEqual(result.viewer_url, "https://files.example.com/token/foundation-day-01.mp3")
        self.assertEqual(result.raw_url, "https://files.example.com/raw/token/foundation-day-01.mp3")

    def test_publisher_accepts_script_path_and_prefix(self) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.assertEqual(command[0], "/custom/publish.sh")
            return subprocess.CompletedProcess(
                command,
                0,
                "https://cdn.example.net/f/meditation.mp3\n",
                "",
            )

        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "meditation.mp3"
            audio.write_bytes(b"audio")
            result = FilePublisher(
                script_path=Path("/custom/publish.sh"),
                url_prefix="https://cdn.example.net/",
                runner=runner,
            ).publish(audio, "meditation.mp3")

        self.assertEqual(result.viewer_url, "https://cdn.example.net/f/meditation.mp3")
        self.assertEqual(result.raw_url, "https://cdn.example.net/raw/f/meditation.mp3")

    def test_publisher_rejects_unexpected_output(self) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, "not a link\n", "")

        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "meditation.mp3"
            audio.write_bytes(b"audio")
            with self.assertRaisesRegex(RuntimeError, "unexpected"):
                FilePublisher(
                    script_path=Path("/fake/publish.sh"),
                    runner=runner,
                ).publish(audio, "meditation.mp3")

    def test_publisher_requires_a_script_path(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "MEDITATION_PUBLISH_SCRIPT"):
            FilePublisher(runner=lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "", ""))


class LocalOnlyPublisherTests(unittest.TestCase):
    def test_local_only_returns_empty_urls(self) -> None:
        publisher = LocalOnlyPublisher()
        result = publisher.publish(Path("/tmp/meditation.mp3"), "meditation.mp3")
        self.assertEqual(result.viewer_url, "")
        self.assertEqual(result.raw_url, "")


if __name__ == "__main__":
    unittest.main()
