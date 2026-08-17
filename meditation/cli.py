from __future__ import annotations

import argparse
import json
from pathlib import Path

from .knowledge_bank import load_knowledge_bank
from .practices import known_practice_keys
from .publisher import FilePublisher, LocalOnlyPublisher
from .script_writer import ScriptWriter
from .service import generate_foundation_session, generate_one_off_session
from .storage import SessionStore
from .tts import HermesVoice


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meditation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    course = subparsers.add_parser("course", help="Generate one ready foundation course session")
    course.add_argument("--day", type=int, required=True)
    course.add_argument("--minutes", type=int, default=10)
    course.add_argument("--theme", default=None, help="Theme for a fresh LLM-written script (optional)")
    course.add_argument("--publish", action="store_true")
    course.add_argument("--provider", default="inworld-meditation")
    course.add_argument("--no-llm", action="store_true", help="Use the saved lesson script instead of fresh LLM writing")

    content_root = Path(__file__).resolve().parents[1] / "content"
    topic_ids = sorted(topic.id for topic in load_knowledge_bank(content_root).topics)
    one_off = subparsers.add_parser(
        "meditation",
        help="Generate a fresh one-off meditation for a knowledge-bank topic",
    )
    one_off.add_argument(
        "--topic",
        required=True,
        choices=topic_ids,
        help="Knowledge-bank topic for the session (anxiety, sleep, stress, ...)",
    )
    one_off.add_argument(
        "--practice",
        choices=sorted(known_practice_keys()),
        help="Practice type (default: first practice the topic fits)",
    )
    one_off.add_argument("--minutes", type=int, default=10)
    one_off.add_argument(
        "--situation",
        default="",
        help="Plain sentence for the situation, e.g. 'before a meeting' (optional)",
    )
    one_off.add_argument("--theme", default=None, help="Theme for the session (optional; drawn from a bank otherwise)")
    one_off.add_argument("--publish", action="store_true")
    one_off.add_argument("--provider", default="inworld-meditation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content_root = Path(__file__).resolve().parents[1] / "content"
    store = SessionStore.from_environment()
    voice = HermesVoice(provider=args.provider)
    publisher = FilePublisher() if args.publish else LocalOnlyPublisher()

    if args.command == "course":
        writer = None if args.no_llm else ScriptWriter()
        result = generate_foundation_session(
            day=args.day,
            minutes=args.minutes,
            theme=args.theme,
            content_root=content_root,
            store=store,
            voice=voice,
            publisher=publisher,
            writer=writer,
        )
    elif args.command == "meditation":
        result = generate_one_off_session(
            topic=args.topic,
            practice=args.practice,
            minutes=args.minutes,
            situation=args.situation,
            theme=args.theme,
            content_root=content_root,
            store=store,
            voice=voice,
            publisher=publisher,
            writer=ScriptWriter(),
        )
    else:
        raise ValueError(f"unsupported command: {args.command}")

    print(
        json.dumps(
            {
                "ok": True,
                "session_id": result.session_id,
                "session_dir": str(result.session_dir),
                "published_url": result.published.viewer_url,
                "raw_url": result.published.raw_url,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
