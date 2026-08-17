from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .delivery import delivery_direction


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class HermesVoice:
    """Synthesize speech through a Hermes Agent TTS command provider.

    The bridge imports Hermes' TTS tool from the Hermes Agent checkout, so
    ``hermes_root`` must point at a Hermes Agent install (override with
    ``HERMES_AGENT_DIR``) and ``python_path`` at its Python interpreter
    (override with ``HERMES_PYTHON``; defaults to the checkout's
    ``.venv/bin/python`` when present, otherwise the running interpreter).
    """

    def __init__(
        self,
        *,
        python_path: Path | None = None,
        bridge_path: Path | None = None,
        hermes_root: Path | None = None,
        provider: str | None = None,
        runner: RunCommand = subprocess.run,
    ) -> None:
        if hermes_root is None:
            configured = os.getenv("HERMES_AGENT_DIR")
            hermes_root = Path(configured) if configured else Path.home() / ".hermes" / "hermes-agent"
        if python_path is None:
            configured = os.getenv("HERMES_PYTHON")
            if configured:
                python_path = Path(configured)
            else:
                venv_python = hermes_root / ".venv" / "bin" / "python"
                python_path = venv_python if venv_python.exists() else Path(sys.executable)
        self.python_path = python_path
        self.bridge_path = bridge_path or Path(__file__).resolve().parents[1] / "scripts" / "hermes_tts_bridge.py"
        self.hermes_root = hermes_root
        self.provider_name = provider or "configured-default"
        self.runner = runner

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        delivery: str = "grounding",
        practice: str | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        directed_text = f"[{delivery_direction(delivery, practice=practice)}] {text.strip()}"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            prefix="meditation-tts-",
            delete=False,
        ) as handle:
            handle.write(directed_text)
            text_path = Path(handle.name)
        command = [
            str(self.python_path),
            str(self.bridge_path),
            "--hermes-root",
            str(self.hermes_root),
            "--text-file",
            str(text_path),
            "--output",
            str(output_path),
        ]
        if self.provider_name != "configured-default":
            command.extend(["--provider", self.provider_name])
        try:
            completed = self.runner(command, capture_output=True, text=True, cwd=str(self.hermes_root))
        finally:
            text_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "voice generation failed")
        try:
            payload: dict[str, Any] = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("voice bridge returned invalid output") from exc
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "voice generation failed"))
        actual_path = Path(str(payload.get("path") or output_path))
        if not actual_path.exists() or actual_path.stat().st_size == 0:
            raise RuntimeError("voice bridge produced no audio")
        return actual_path
