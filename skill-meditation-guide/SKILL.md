---
name: meditation-guide
description: Use when the user asks for a guided meditation or meditation audio.
version: 3.1.0
author: Bob
license: MIT
metadata:
  hermes:
    tags: [meditation, audio, knowledge-bank, published-files]
    related_skills: [meditation-feature-development]
---

# Meditation Guide

## Use this skill when

- The user asks for a guided meditation or meditation audio.
- The user asks for a session about a topic or situation (anxiety, sleep, stress, anger, self-compassion, focus, relationships, grief).
- The user gives feedback about teaching, wording, silence, voice, or pacing.

## How a meditation is made

The system has a knowledge bank of teaching points, practices, and plain-language topics. The writer reads the whole bank and writes fresh words every time. Two meditations are never identical.

A request needs a **topic**. The topics are:

- anxiety
- sleep
- stress
- anger
- self-compassion
- focus
- relationships
- grief

A request can also name a **situation**, a plain sentence about what is happening (for example "lethargic before a family event I don't want to go to but have to"). The writer uses the situation to pick the best practice and to write words that fit the moment.

The practice (breath, body scan, walking, sleep, loving kindness) is chosen automatically from the situation. You can also name one explicitly.

## Generate and publish a meditation

Run from this repository root:

```bash
PYTHONPATH=. python3 -m meditation.cli meditation \
  --topic anxiety --minutes 10 --situation "before a meeting" --publish
```

- `--topic` is required. Pick from: anger, anxiety, focus, grief, relationships, self-compassion, sleep, stress.
- `--minutes` is the length.
- `--situation` is optional, a plain sentence. Include it when the user describes what is happening, so the practice and words fit.
- `--practice` is optional. Omit it to let the writer choose the best practice from the situation.
- `--theme` is optional, a plain sensory detail. Omit it to let the bank choose.
- `--publish` voices the script and publishes it. Omit it to render audio locally only.

Prerequisites: a Hermes Agent install with a configured TTS command provider (see the README), a `DEEPSEEK_API_KEY` (or `MEDITATION_LLM_BASE_URL` / `MEDITATION_LLM_MODEL` overrides), and `ffmpeg` on PATH. Publishing additionally needs `MEDITATION_PUBLISH_SCRIPT` pointing at a script that prints the viewer URL on its last line; without it, use `LocalOnlyPublisher` (the default when `--publish` is omitted).

## How to handle a request

1. Identify the topic. If the user names one (anxiety, sleep, stress, ...), use it. If they describe a situation without naming a topic, choose the topic that fits (for example "lethargic before a family event I don't want to go to but have to" is self-compassion).
2. Use their words as the situation.
3. Pick a length. If they do not say, a sensible default is 10 minutes. Short moments (before an event) can be 5 minutes.
4. Run the command with `--publish` and their exact words as the situation.
5. Return the published link. If they ask to read the script first, show it, but by default deliver the audio link directly.

## Content rules (the writer enforces these; do not override them)

- One teaching point per session, one practice, one plain theme detail.
- Plain, conversational English. No poetry, no mysticism, no cliches, no metaphors, no poster lines.
- The voice can carry tone naturally. There is no flat-read rule.
- Welcome is its own short line with a 3.0 second gap.
- The writer chooses where the longer pauses go and how long each is.
- No repeated lines.
- No invented weather, time, surroundings, or local facts.
- No medical claims, no promises of calm, no demands to feel a certain way.
- For anxiety: ordinary worry uses breath/body focus; rising distress moves attention outward (sounds, sight, feet); panic, derealisation, or flashbacks means a grounding session or human support, never an intense inward practice.
- Never author new knowledge-bank content without the user's approval.

## Feedback

Record specific feedback in the session work. Examples:

- too much talking
- pauses too long
- teaching too basic
- teaching felt vague
- voice sounded clipped
- theme felt forced

Load the development skill before changing the feature or course source.

## Completion checks

- The command succeeds.
- The generated session lasts the requested time.
- A published browser link is returned (or a local audio file when not publishing).
- The raw audio bytes were verified when the file was first published or republished.
