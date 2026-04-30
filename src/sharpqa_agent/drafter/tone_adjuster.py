"""Tone adjuster — provides tone variant configurations for email generation."""

from __future__ import annotations

from sharpqa_agent.core.models import ToneVariant


def get_tone_variants() -> list[ToneVariant]:
    """Return all available tone variants for parallel generation.

    Returns:
        List of ToneVariant enum values.
    """
    return [ToneVariant.DIRECT, ToneVariant.CONSULTATIVE, ToneVariant.FRIENDLY]


def get_default_tone() -> ToneVariant:
    """Return the default tone variant.

    Returns:
        The default ToneVariant (DIRECT).
    """
    return ToneVariant.DIRECT
