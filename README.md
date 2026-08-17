# hermes-meditation

A chat-driven guided meditation generator for [Hermes Agent](https://hermes-agent.nousresearch.com/docs).

Say what you need in plain words ("10-minute anxiety meditation before a meeting") and the generator writes a fresh script, checks it against safety rules, speaks it with a voice already configured in Hermes, renders it to an exact-length audio file with real pauses, and returns a link or a local file.

Two meditations are never identical. Every session is written fresh from a knowledge bank of science, psychological topics, teaching points, and practices.

## What you need

- Python 3.12+
- A Hermes Agent install with a TTS command provider configured (any voice Hermes can use)
- An LLM API key for writing scripts (`DEEPSEEK_API_KEY`, or override with `MEDITATION_LLM_BASE_URL` / `MEDITATION_LLM_MODEL` for any OpenAI-compatible endpoint)
- `ffmpeg` on your PATH for audio rendering
- Optional: a publish script for public file links (`MEDITATION_PUBLISH_SCRIPT`)

## Install

```bash
git clone https://github.com/jannadeeble/hermes-meditation.git
cd hermes-meditation
pip install -e .
```

## Generate a meditation

```bash
meditation meditation --topic anxiety --minutes 10 --situation "before a meeting"
```

Without `--publish`, the rendered audio is saved locally (session files land under `$HERMES_HOME/meditation/sessions`). Add `--publish` and set `MEDITATION_PUBLISH_SCRIPT` to a script that prints the viewer URL on its last line:

```bash
meditation meditation --topic sleep --minutes 5 --situation "lying in bed worrying about tomorrow" --publish
```

### Topics

`anger`, `anxiety`, `focus`, `grief`, `relationships`, `self-compassion`, `sleep`, `stress`

### Options

- `--practice` — pick the practice explicitly (breath_anchor, body_scan, walking, sleep, loving_kindness, focus). Omit to let the writer choose from the situation.
- `--situation` — a plain sentence about what is happening, so the practice and words fit the moment.
- `--theme` — an optional sensory detail. Omit to let the bank choose.
- `--minutes` — session length.

### Course mode

The repo also ships a 30-day foundation course (`meditation course --day N`). Days have fixed objectives and evidence cards; by default each render writes fresh words within the day's practice type (`--no-llm` uses the saved reviewed script).

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | LLM key for script writing | read from `~/.hermes/.env` if set |
| `MEDITATION_LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.deepseek.com` |
| `MEDITATION_LLM_MODEL` | Writer model | `deepseek-v4-flash` |
| `HERMES_AGENT_DIR` | Hermes Agent checkout used by the voice bridge | `~/.hermes/hermes-agent` |
| `HERMES_PYTHON` | Python interpreter for the voice bridge | the checkout's `.venv/bin/python`, else the running interpreter |
| `HERMES_ENV_PATH` | Fallback `.env` for the API key | `~/.hermes/.env` |
| `MEDITATION_PUBLISH_SCRIPT` | Script that prints a viewer URL for `--publish` | none (local render only) |
| `MEDITATION_PUBLISH_URL_PREFIX` | Base prefix for the raw URL derivation | `https://files.example.com/` |

## Content rules

The writer enforces these; the tests verify them:

- One teaching point per session, one practice, one plain theme detail.
- Plain, conversational English. No poetry, mysticism, cliches, metaphors, or poster lines.
- No repeated lines.
- No invented weather, time, surroundings, or local facts.
- No medical claims, no promises of calm, no demands to feel a certain way.
- For anxiety: ordinary worry uses breath/body focus; rising distress moves attention outward (sounds, sight, feet); panic, derealisation, or flashbacks means a grounding session or human support, never an intense inward practice.
- Sleep practice forbids a brightening delivery; the session never pushes energy up.

## Test

```bash
python -m unittest discover -s tests -v
```

## Layout

- `meditation/` — the engine: script writer, validation, practices, renderer, voice bridge, storage, publisher
- `content/` — the knowledge bank (markdown + machine-readable JSON), foundation course, teaching and evidence cards
- `skill-meditation-guide/` — a Hermes skill that teaches the agent when and how to run the generator
- `scripts/hermes_tts_bridge.py` — imports Hermes' TTS tool so the voice matches your Hermes setup
- `docs/ARCHITECTURE.md` — how the pieces fit

## License

MIT
