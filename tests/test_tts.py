import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from meditation.tts import HermesVoice


class HermesVoiceTests(unittest.TestCase):
    def test_voice_bridge_receives_text_file_and_output_path(self) -> None:
        captured_command: list[str] = []
        captured_text: list[str] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured_command.extend(command)
            text_file = Path(command[command.index("--text-file") + 1])
            captured_text.append(text_file.read_text())
            output = Path(command[command.index("--output") + 1])
            output.write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "path": str(output)}), "")

        with tempfile.TemporaryDirectory() as temp:
            voice = HermesVoice(
                python_path=Path("/fake/python"),
                bridge_path=Path("/fake/bridge.py"),
                hermes_root=Path("/fake/hermes"),
                provider="inworld-meditation",
                runner=runner,
            )
            output = voice.synthesize(
                "A short teaching.",
                Path(temp) / "clip.audio",
                delivery="encouraging",
            )

            self.assertEqual(output.read_bytes(), b"audio")
            self.assertIn("--text-file", captured_command)
            self.assertEqual(captured_command[captured_command.index("--provider") + 1], "inworld-meditation")
            self.assertEqual(len(captured_text), 1)
            self.assertTrue(captured_text[0].startswith("["))
            self.assertIn("lift in energy", captured_text[0].lower())
            self.assertTrue(captured_text[0].endswith("A short teaching."))

    def test_sleep_encouraging_is_gentler_with_no_lift(self) -> None:
        captured_text: list[str] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            text_file = Path(command[command.index("--text-file") + 1])
            captured_text.append(text_file.read_text())
            output = Path(command[command.index("--output") + 1])
            output.write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "path": str(output)}), "")

        with tempfile.TemporaryDirectory() as temp:
            voice = HermesVoice(
                python_path=Path("/fake/python"),
                bridge_path=Path("/fake/bridge.py"),
                hermes_root=Path("/fake/hermes"),
                runner=runner,
            )
            voice.synthesize(
                "Rest into the bed.",
                Path(temp) / "clip.audio",
                delivery="encouraging",
                practice="sleep",
            )

        self.assertIn("no lift", captured_text[0].lower())
        self.assertNotIn("lift in energy", captured_text[0].lower())
        self.assertIn("warmly reassuring", captured_text[0].lower())

    def test_sleep_practice_rejects_brightening_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            voice = HermesVoice(
                python_path=Path("/fake/python"),
                bridge_path=Path("/fake/bridge.py"),
                hermes_root=Path("/fake/hermes"),
            )
            with self.assertRaisesRegex(ValueError, "sleep practice"):
                voice.synthesize(
                    "Return to the day.",
                    Path(temp) / "clip.audio",
                    delivery="brightening",
                    practice="sleep",
                )

    def test_brightening_stays_allowed_for_other_practices(self) -> None:
        captured_text: list[str] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            text_file = Path(command[command.index("--text-file") + 1])
            captured_text.append(text_file.read_text())
            output = Path(command[command.index("--output") + 1])
            output.write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "path": str(output)}), "")

        with tempfile.TemporaryDirectory() as temp:
            voice = HermesVoice(
                python_path=Path("/fake/python"),
                bridge_path=Path("/fake/bridge.py"),
                hermes_root=Path("/fake/hermes"),
                runner=runner,
            )
            voice.synthesize(
                "Carry this into the day.",
                Path(temp) / "clip.audio",
                delivery="brightening",
                practice="walking",
            )

        self.assertIn("brighten", captured_text[0].lower())

    def test_voice_bridge_failure_is_reported(self) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 1, "", "voice failed")

        with tempfile.TemporaryDirectory() as temp:
            voice = HermesVoice(
                python_path=Path("/fake/python"),
                bridge_path=Path("/fake/bridge.py"),
                hermes_root=Path("/fake/hermes"),
                runner=runner,
            )
            with self.assertRaisesRegex(RuntimeError, "voice failed"):
                voice.synthesize("Text", Path(temp) / "clip.audio")


if __name__ == "__main__":
    unittest.main()
