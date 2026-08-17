from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path, required=True)
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider")
    args = parser.parse_args()

    sys.path.insert(0, str(args.hermes_root))
    from tools.tts_tool import (
        _generate_command_tts,
        _load_tts_config,
        _resolve_command_provider_config,
        text_to_speech_tool,
    )

    text = args.text_file.read_text(encoding="utf-8")
    if args.provider:
        tts_config = _load_tts_config()
        provider_config = _resolve_command_provider_config(args.provider, tts_config)
        if provider_config is None:
            print(json.dumps({"ok": False, "error": f"voice provider is unavailable: {args.provider}"}))
            return 1
        try:
            actual = _generate_command_tts(
                text=text,
                output_path=str(args.output),
                provider_name=args.provider,
                config=provider_config,
                tts_config=tts_config,
            )
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 1
        print(json.dumps({"ok": True, "path": actual}))
        return 0

    result = json.loads(
        text_to_speech_tool(
            text=text,
            output_path=str(args.output),
        )
    )
    if not result.get("success"):
        print(json.dumps({"ok": False, "error": result.get("error") or "voice generation failed"}))
        return 1
    actual = result.get("file_path") or result.get("path") or str(args.output)
    print(json.dumps({"ok": True, "path": actual}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
