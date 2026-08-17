from __future__ import annotations

DELIVERY_DIRECTIONS: dict[str, str] = {
    "settling": (
        "quietly, soft and warm, with a gentle tone at a natural unhurried pace"
    ),
    "grounding": (
        "calm and grounded, in a low steady tone, with clear articulation and a soft, unhurried pace"
    ),
    "spacious": (
        "soft and spacious, with gentle pitch variation and a quiet, unhurried pace"
    ),
    "encouraging": (
        "warmly reassuring, with a gentle lift in energy, calm and unhurried"
    ),
    "brightening": (
        "gently brighten the energy, with a little more pitch range and a clear warm tone, still calm and unhurried"
    ),
    "closing": (
        "warm, settled, and reassuring, with a gentle falling pitch and an unhurried pace"
    ),
}

# Sleep and rest practices get gentler delivery: no lift, no brightening.
# The sleep practice forbids "brightening" outright and maps "encouraging"
# to a softer, flatter reassurance so the session never pushes energy up.
SLEEP_DELIVERY_OVERRIDES: dict[str, str] = {
    "encouraging": (
        "warmly reassuring, gentle, unhurried, with no lift"
    ),
}

SLEEP_FORBIDDEN_DELIVERIES: frozenset[str] = frozenset({"brightening"})


def known_delivery_keys() -> tuple[str, ...]:
    return tuple(DELIVERY_DIRECTIONS)


def delivery_direction(delivery: str, practice: str | None = None) -> str:
    try:
        direction = DELIVERY_DIRECTIONS[delivery]
    except KeyError as exc:
        raise ValueError(f"unknown meditation delivery: {delivery}") from exc
    if practice == "sleep":
        if delivery in SLEEP_FORBIDDEN_DELIVERIES:
            raise ValueError(
                f"delivery '{delivery}' is not allowed for the sleep practice"
            )
        return SLEEP_DELIVERY_OVERRIDES.get(delivery, direction)
    return direction
