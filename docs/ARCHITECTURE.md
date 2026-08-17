# Guided Meditation Architecture

## Product boundary

Version 1 lives in normal Hermes chat.

The user asks for a meditation. Hermes loads the meditation skill and runs the generator. The generator makes the audio with the voice provider already configured in Hermes. It can publish the audio through a configured file service (optional). Hermes returns the published link or a local audio file.

There is no separate web page, player, schedule service, or meditation web API in this version.

## Two generation paths

- **Course path** (`course`): the 30-day learning journey. Days have fixed objectives, practice types, and evidence cards. By default each render writes fresh LLM words within the day's practice type; `--no-llm` renders the saved reviewed script.
- **One-off path** (`meditation`): any knowledge-bank topic, any time. The user names a topic (anxiety, sleep, stress, ...), a length, and an optional practice (the first practice the topic fits is used when omitted), situation, and theme. The topic's teaching points are selected from the knowledge bank and fresh words are written every render.

## Main content rule

Every session has one to three teaching points (course days keep one fixed objective; one-off sessions take one to three points from the selected knowledge-bank topic), one main practice, and one plain sensory theme detail.

Foundation lessons are written and reviewed one at a time. The 30-day file records the whole course shape, but only lessons marked `ready` can be rendered. At present, Day 1 and Day 16 are ready. Days 2 to 30 are placeholders.

## LLM script writing

`meditation/script_writer.py` writes every fresh script:

1. It looks up the practice spec (`meditation/practices.py`): posture, attention target, cue vocabulary, forbidden cues, extra rules, themed bank.
2. The theme comes from the caller or from the practice's themed bank.
3. It calls the DeepSeek chat API (key `DEEPSEEK_API_KEY` from the Hermes `.env`) with a strict system prompt and a practice-specific prompt. The system prompt is the fixed writing rules plus the full text of `content/knowledge-bank.md`, read from disk on every write call so the writer always sees the whole bank. One-off calls also pass a topic brief selected from `content/knowledge-bank.json`: the topic name, situation, 1-3 teaching points with explanations, and the practice's exact return method. The model returns strict JSON: a `blocks` array with `text`, `pause_instruction`, `pause_seconds`, and a delivery label. The writer decides where longer pauses go and how long each is; `pause_seconds` is honoured exactly.
4. `meditation/validation.py` runs the content guardrails, including the light topic checks when the stage arc is required: the teaching stage must be present with spoken text, and the wandering return must not name another practice's anchor (a sleep script returning to "the next step" is rejected; paraphrasing sleep's own bed anchor is fine). The sleep practice also cannot use the `brightening` delivery. The writer then checks the delivery arc and the time budget before voice generation: block count, word count, number of practice pauses, and estimated minimum duration must fit the requested length.
5. On a rule violation the writer retries once with the problems fed back, then raises. Nothing is rendered or voiced until the script passes.

This is what gives the feature variance: two meditations of the same practice are written fresh each time, within the same safety frame.

## Data flow

1. The command loads the course file (course path) or the practice spec (one-off path).
2. It refuses any course lesson that is not marked ready.
3. It writes the script (LLM path) or loads the saved reviewed blocks (`--no-llm`).
4. It creates a new session under the active Hermes profile.
5. It turns each delivery label into a vetted voice direction, then sends the complete directed speech block to the meditation's selected voice provider. Punctuation stays intact so the voice can understand the whole sentence.
6. It measures the real speech length.
7. It distributes the remaining time across the lesson's silence weights.
8. It joins speech and silence into an exact-length wave file and an MP3 file.
9. It writes the score and session record beside the audio.
10. It publishes the MP3 with the configured file publisher when requested.
11. It returns both the browser link and direct audio link as structured output.

## Source of truth

- `content/foundation-course.json`: course order, lesson status, objectives, practices, scripts, and pause weights
- `content/evidence-cards.json`: reviewed teaching claims, sources, approved spoken wording, and stronger wording that is not supported (course path)
- `content/knowledge-bank.md`: the approved bank of topics, teaching points, practices, and writing rules; the writer's system prompt carries this whole document
- `content/knowledge-bank.json`: machine-readable bank (topics, points, fit practices, return hints, safety notes) used to build one-off topic briefs
- `meditation/curriculum.py`: course loading and the ready-only gate
- `meditation/knowledge_bank.py`: bank loading, validation, and one-off topic-brief selection
- `meditation/practices.py`: practice types, safety rules, cue vocabularies, forbidden cues, themed banks
- `meditation/script_writer.py`: LLM script writing with validation and one retry
- `meditation/validation.py`: guardrail checks shared by the writer and the tests
- `meditation/renderer.py`: measured speech, silence allocation, and exact audio assembly
- `meditation/tts.py`: bridge to the selected voice provider without changing the voice used elsewhere in Hermes
- `meditation/storage.py`: profile-specific session storage
- `meditation/publisher.py`: published file links
- `meditation/service.py`: one complete generation run (course and one-off)
- `meditation/cli.py`: chat-facing command

## Scientific claims

Body and brain explanations are allowed when they are supported by a reviewed source. A claim must first be added to the evidence-card file. The lesson refers to that card and uses wording no stronger than the reviewed claim.

The system does not ban words merely because they describe effects on the body or brain. It bans claims that are stronger than their source, such as promising a permanent change from one session.

## Walking sessions

This is a personal feature. Walking sessions do not need stock warnings about eyes, paths, roads, or cliffs. They should still be written as walking practices, without cues that depend on being seated or still.

## Timing

Long practice silence is controlled by code. Natural pauses and intonation within a spoken line are left to the voice provider.

Each speech block has:

- text
- an optional practice instruction spoken immediately before a long pause
- a minimum pause after it
- a pause weight
- a minimum session length in minutes

A session length is chosen from the lesson's supported range. Day 1 supports 5, 10, 15, and 20 minutes. Blocks whose minimum session length is above the requested length are dropped, so a short session keeps the core arc and longer sessions keep the full script.

Each session may also define a short opening silence. Day 1 uses five seconds, then a brief welcome with a 3.0-second gap before the body setup. The soundscape fades in during this opening silence so it is at full level when the voice begins.

Ordinary sentences are separate blocks with fixed 4.5-second gaps and zero pause weight. Only a block with an explicit practice instruction can receive a long or extendable pause. A pause longer than eight seconds also requires an instruction. This prevents an introduction or teaching sentence from falling into unexplained silence.

For LLM-written sessions, the writer decides where the longer pauses go and how long each one is. It sets `pause_seconds` on practice-pause blocks and the system honours that value exactly (weight 0, so the allocator never inflates it). Longer sessions prompt the writer to use longer or more pauses; any time left unused becomes trailing quiet at the end.

Each complete spoken line, including any practice instruction, is voiced in one request. Commas and semicolons remain in the text so the voice can use the full sentence meaning to choose natural pauses, emphasis, and pitch. The renderer never splits a sentence into separately voiced fragments.

After the speech is generated, the renderer measures every clip. It keeps all fixed gaps and minimum practice pauses, then distributes remaining time across weighted pauses when weights exist. If speech and minimum pauses cannot fit, generation fails. The voice provider guides the delivery and within-line pacing during generation. The renderer never stretches finished speech. Pacing comes from complete spoken lines, the provider's reading of punctuation, the provider's voice direction, and deliberate gaps between blocks.

The final wave file must be within 0.05 seconds of the requested length. MP3 encoder padding can add a very small difference.

## Soundscape

Each lesson may declare a soundscape file in the configured file area. Day 1 uses a multi-hour 432 Hz ambient track with no melody, designed to be homogeneous so any timed chunk works.

The renderer pulls a chunk of exactly the session length from a random point in the soundscape. It fades the chunk in over the opening silence and fades it out over the final seconds, then mixes it quietly under the voice at 15 percent volume. The final wave file keeps the exact requested length.

The chosen start position and volume are saved in the session score so any render can be reproduced.

## Voice

Meditations use the voice provider already configured in Hermes (the author's setup uses a warm, calm voice). The writer chooses one of six safe delivery styles for every block: settling, grounding, spacious, encouraging, brightening, or closing. Code maps those labels to natural-language directions for tone, pitch, energy, and pace. The directions stay soft and soothing across the whole arc. The sleep practice is gentler still: `brightening` is forbidden for sleep (rejected by validation before any voice credit is spent), and `encouraging` maps to "warmly reassuring, gentle, unhurried, with no lift" so the session never pushes energy up. The first block settles, the final block closes, and longer scripts must use at least three styles. The provider's balanced delivery mode allows these changes to be heard without the inconsistency of its creative mode. A fixed calm direction remains as a fallback for text that has no block direction. The choice is local to this feature. The selected provider and each block's delivery label are saved in the session record.

## Storage

Sessions live below the active `HERMES_HOME`. This keeps different Hermes profiles separate. Every session stores:

- manifest
- timed score
- speech clips
- silence clips
- exact wave file
- MP3 file
- published link

The browser never chooses a storage path.

## Course editing procedure

To add the next lesson:

1. Pick the next planned day. Do not skip days.
2. Research the one teaching point.
3. Add or reuse one reviewed evidence card.
4. Write the objective and one main practice.
5. Write six to ten natural speech blocks.
6. Split rushed passages into short spoken lines with ordinary fixed gaps.
7. Before every long pause, state exactly what the listener should practise during the silence.
8. Give only instructed practice pauses a pause weight.
9. Mark only that lesson ready.
10. Run the full unit test suite.
11. Generate a ten-minute real audio file.
12. Listen to the whole file and record changes before starting the following day.

Course content should grow one lesson at a time. Do not generate all 30 scripts in advance.

The spoken meditation must stand on its own. Do not call it the first lesson, second lesson, Day 1, or another course position. Course numbering belongs in records and file names, not in the meditation itself.

The arrival should gently prepare the listener before teaching begins. It starts with short silence and a brief welcome, then sets up the body, says what to do with the eyes, allows adjustments, and briefly explains the practice ahead. The welcome should not create a long pause before useful guidance begins.

## Test boundaries

Unit tests cover:

- 30 ordered course placeholders
- only written lessons being renderable
- evidence-card links
- exact silence allocation
- rejection of overlong speech
- exact wave and MP3 duration
- soundscape chunk mixing, fade edges, and too-short rejection
- profile isolation
- voice bridge errors
- published link handling
- a complete generation run with a fake voice
- complete punctuated lines reaching the voice provider without being split into fragments
- varied delivery labels reaching the voice bridge
- the voice provider's per-block direction replacing the fixed fallback direction
- rejection and rewrite of scripts that cannot fit the requested time before voice credits are spent

A release check also uses the real local voice and verifies the published bytes.

## Deliberate omissions

Version 1 has no:

- dedicated web page
- second scheduler
- synthetic healing frequencies
- automatic generation of unwritten course days
- separate text model client
- shared cross-profile data folder

Hermes's main model handles any future custom writing. The renderer remains mechanical and checked.
