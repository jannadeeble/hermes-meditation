from __future__ import annotations

from collections.abc import Sequence

from .models import ScriptBlock


def allocate_silence(
    blocks: Sequence[ScriptBlock],
    *,
    speech_seconds: float,
    target_seconds: float,
) -> tuple[float, ...]:
    minimums = [block.pause_min_seconds for block in blocks]
    required = speech_seconds + sum(minimums)
    if required > target_seconds + 1e-6:
        raise ValueError(
            f"spoken audio is too long: {required:.2f}s required for a {target_seconds:.2f}s session"
        )
    extra = max(0.0, target_seconds - required)
    weight_total = sum(block.pause_weight for block in blocks)
    instructed = any(block.pause_instruction for block in blocks)
    if extra > 1e-6 and weight_total <= 0 and not instructed:
        raise ValueError("session has spare time but no instructed practice pause")
    if weight_total <= 0:
        # LLM-chosen exact pauses: honor them and let spare time become
        # trailing quiet at the end of the session.
        return tuple(minimums)
    pauses = tuple(
        minimum + (extra * block.pause_weight / weight_total if block.pause_weight > 0 else 0.0)
        for block, minimum in zip(blocks, minimums, strict=True)
    )
    return pauses
