from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from .models import RenderResult, ScriptBlock
from .score import allocate_silence

class VoiceProvider(Protocol):
    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        delivery: str = "grounding",
        practice: str | None = None,
    ) -> Path: ...


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "audio command failed"
        raise RuntimeError(message)


def audio_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"could not measure {path}")
    return float(completed.stdout.strip())


def _write_silence(path: Path, seconds: float) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{seconds:.6f}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


class MeditationRenderer:
    def __init__(
        self,
        voice: VoiceProvider,
        *,
        speech_tempo: float = 1.0,
        practice: str | None = None,
    ) -> None:
        if speech_tempo < 0.5 or speech_tempo > 1.0:
            raise ValueError("speech tempo must be between 0.5 and 1.0")
        self.voice = voice
        self.speech_tempo = speech_tempo
        self.practice = practice

    def render(
        self,
        blocks: tuple[ScriptBlock, ...],
        *,
        opening_silence_seconds: float = 0.0,
        target_seconds: float,
        output_dir: Path,
        soundscape: Path | None = None,
        soundscape_start_seconds: float | None = None,
        soundscape_volume: float = 0.15,
        soundscape_fade_out_seconds: float = 8.0,
    ) -> RenderResult:
        if not blocks:
            raise ValueError("at least one script block is required")
        if target_seconds <= 0:
            raise ValueError("target duration must be positive")
        if opening_silence_seconds < 0:
            raise ValueError("opening silence cannot be negative")

        output_dir.mkdir(parents=True, exist_ok=True)
        parts_dir = output_dir / "parts"
        parts_dir.mkdir(parents=True, exist_ok=True)

        speech_wavs: list[Path] = []
        speech_seconds: list[float] = []
        for index, block in enumerate(blocks, start=1):
            raw_path = self.voice.synthesize(
                block.spoken_text,
                parts_dir / f"speech-{index:02d}.audio",
                delivery=block.delivery,
                practice=self.practice,
            )
            wav_path = parts_dir / f"speech-{index:02d}.wav"
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(raw_path),
                    "-filter:a",
                    f"atempo={self.speech_tempo:.6f}",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_path),
                ]
            )
            speech_wavs.append(wav_path)
            speech_seconds.append(audio_duration(wav_path))

        pauses = allocate_silence(
            blocks,
            speech_seconds=sum(speech_seconds) + opening_silence_seconds,
            target_seconds=target_seconds,
        )

        ordered_parts: list[Path] = []
        if opening_silence_seconds > 0:
            opening_path = parts_dir / "silence-opening.wav"
            _write_silence(opening_path, opening_silence_seconds)
            ordered_parts.append(opening_path)
        for index, (speech_path, pause) in enumerate(
            zip(speech_wavs, pauses, strict=True), start=1
        ):
            ordered_parts.append(speech_path)
            silence_path = parts_dir / f"silence-{index:02d}.wav"
            _write_silence(silence_path, pause)
            ordered_parts.append(silence_path)

        concat_file = parts_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{part.as_posix()}'\n" for part in ordered_parts),
            encoding="utf-8",
        )
        joined_path = parts_dir / "joined.wav"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(joined_path),
            ]
        )

        voice_track = joined_path
        resolved_start: float | None = None
        if soundscape is not None:
            soundscape_seconds = audio_duration(soundscape)
            if soundscape_seconds < target_seconds:
                raise ValueError(
                    f"soundscape is too short: {soundscape_seconds:.2f}s for a {target_seconds:.2f}s session"
                )
            if soundscape_start_seconds is None:
                soundscape_start_seconds = 0.0
            if soundscape_start_seconds < 0 or soundscape_start_seconds + target_seconds > soundscape_seconds + 0.05:
                raise ValueError("soundscape start is outside the audio file")
            resolved_start = soundscape_start_seconds
            chunk_path = parts_dir / "soundscape-chunk.wav"
            fade_in = max(0.0, opening_silence_seconds)
            fade_out_start = max(0.0, target_seconds - soundscape_fade_out_seconds)
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{soundscape_start_seconds:.3f}",
                    "-i",
                    str(soundscape),
                    "-t",
                    f"{target_seconds:.6f}",
                    "-af",
                    (
                        f"volume={soundscape_volume:.6f},"
                        f"afade=t=in:st=0:d={fade_in:.3f},"
                        f"afade=t=out:st={fade_out_start:.3f}:d={soundscape_fade_out_seconds:.3f}"
                    ),
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(chunk_path),
                ]
            )
            mixed_path = parts_dir / "mixed.wav"
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(joined_path),
                    "-i",
                    str(chunk_path),
                    "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                    "-map",
                    "[a]",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(mixed_path),
                ]
            )
            voice_track = mixed_path

        wav_path = output_dir / "meditation.wav"
        mp3_path = output_dir / "meditation.mp3"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(voice_track),
                "-af",
                "apad",
                "-t",
                f"{target_seconds:.6f}",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ]
        )
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(wav_path),
                "-t",
                f"{target_seconds:.6f}",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(mp3_path),
            ]
        )

        if abs(audio_duration(wav_path) - target_seconds) > 0.05:
            raise RuntimeError("rendered WAV has the wrong duration")
        return RenderResult(
            wav_path=wav_path,
            mp3_path=mp3_path,
            speech_seconds=tuple(speech_seconds),
            pause_seconds=pauses,
            opening_silence_seconds=opening_silence_seconds,
            soundscape_start_seconds=resolved_start,
            soundscape_volume=soundscape_volume if soundscape is not None else None,
        )
