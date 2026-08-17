from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


_SESSION_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_environment(cls) -> "SessionStore":
        hermes_home = os.environ.get("HERMES_HOME")
        if not hermes_home:
            hermes_home = str(Path.home() / ".hermes")
        return cls(Path(hermes_home).expanduser().resolve() / "meditation" / "sessions")

    def create_session(self, session_id: str, manifest: dict[str, Any]) -> Path:
        if not _SESSION_ID.fullmatch(session_id):
            raise ValueError("invalid session identifier")
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=False)
        (session_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return session_dir

    def write_manifest(self, session_id: str, manifest: dict[str, Any]) -> Path:
        if not _SESSION_ID.fullmatch(session_id):
            raise ValueError("invalid session identifier")
        manifest_path = self.root / session_id / "manifest.json"
        if not manifest_path.parent.is_dir():
            raise ValueError(f"unknown session identifier: {session_id}")
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest_path

    def recent_teaching_card_ids(self, *, limit: int = 6) -> tuple[str, ...]:
        if limit < 1 or not self.root.is_dir():
            return ()
        manifests: list[tuple[str, str]] = []
        for manifest_path in self.root.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            card_id = str(manifest.get("teaching_card_id") or "").strip()
            if not card_id:
                continue
            created_at = str(manifest.get("created_at") or "")
            manifests.append((created_at, card_id))

        seen: set[str] = set()
        recent: list[str] = []
        for _, card_id in sorted(manifests, reverse=True):
            if card_id in seen:
                continue
            seen.add(card_id)
            recent.append(card_id)
            if len(recent) == limit:
                break
        return tuple(recent)

    def recent_topic_point_ids(self, *, limit: int = 6) -> tuple[str, ...]:
        """Recently used knowledge-bank point ids, newest first, unique.

        Reads the ``point_ids`` list recorded in one-off session manifests so
        the topic brief selection can avoid repeating the same teaching point
        when other fitting points exist.
        """
        if limit < 1 or not self.root.is_dir():
            return ()
        manifests: list[tuple[str, list[str]]] = []
        for manifest_path in self.root.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            raw_ids = manifest.get("point_ids")
            if not isinstance(raw_ids, list):
                continue
            ids = [str(point_id) for point_id in raw_ids if str(point_id).strip()]
            if not ids:
                continue
            created_at = str(manifest.get("created_at") or "")
            manifests.append((created_at, ids))

        seen: set[str] = set()
        recent: list[str] = []
        for _, ids in sorted(manifests, reverse=True):
            for point_id in ids:
                if point_id in seen:
                    continue
                seen.add(point_id)
                recent.append(point_id)
            if len(recent) >= limit:
                break
        return tuple(recent[:limit])
