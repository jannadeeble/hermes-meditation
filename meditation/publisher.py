from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class PublishedFile:
    viewer_url: str
    raw_url: str


class FilePublisher:
    """Publish a rendered audio file through an external publish script.

    Configure the script path with the ``MEDITATION_PUBLISH_SCRIPT``
    environment variable. The script must print the viewer URL on its last
    line. The raw URL is derived by inserting ``raw/`` after the configured
    base prefix (``MEDITATION_PUBLISH_URL_PREFIX``, default
    ``https://files.example.com/``). Override the prefix to match your file
    host when it follows the same token/raw layout.
    """

    def __init__(
        self,
        *,
        script_path: Path | None = None,
        url_prefix: str | None = None,
        runner: RunCommand = subprocess.run,
    ) -> None:
        configured = os.getenv("MEDITATION_PUBLISH_SCRIPT")
        if script_path is None and configured:
            script_path = Path(configured)
        if script_path is None:
            raise RuntimeError(
                "no publish script configured: set MEDITATION_PUBLISH_SCRIPT "
                "or use LocalOnlyPublisher for a local render"
            )
        self.script_path = script_path
        self.url_prefix = url_prefix or os.getenv("MEDITATION_PUBLISH_URL_PREFIX", "https://files.example.com/")
        self.runner = runner

    def publish(self, file_path: Path, display_name: str) -> PublishedFile:
        completed = self.runner(
            [str(self.script_path), str(file_path), display_name],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "publishing failed")
        viewer_url = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        prefix = self.url_prefix
        if not viewer_url.startswith(prefix):
            raise RuntimeError("publisher returned unexpected output")
        raw_url = prefix + "raw/" + viewer_url[len(prefix):]
        return PublishedFile(viewer_url=viewer_url, raw_url=raw_url)


class LocalOnlyPublisher:
    def publish(self, file_path: Path, display_name: str) -> PublishedFile:
        return PublishedFile(viewer_url="", raw_url="")
