"""Shared item name normalization utilities."""

import re

_LEADING_DESCRIPTORS = {
    "organic",
    "fresh",
    "whole",
    "large",
    "small",
}
_TRAILING_FILLER = {"pack", "packs", "count", "ct", "pkg", "pk", "bag", "bottle", "can"}
_MEASURE_TOKEN = re.compile(r"^\d+(?:\.\d+)?(?:oz|lb|lbs|g|kg|ml|l|ct)$")
_SIMPLE_NUMERIC = re.compile(r"^\d+(?:\.\d+)?%?$")


def normalize_item_name(item_name: str) -> str:
    """Normalize item names into a canonical identity key."""
    cleaned = re.sub(r"[^a-z0-9% ]+", " ", item_name.lower())
    tokens = [token for token in cleaned.split() if token]

    while tokens and tokens[0] in _LEADING_DESCRIPTORS:
        tokens.pop(0)

    while tokens and (
        tokens[-1] in _TRAILING_FILLER
        or _MEASURE_TOKEN.match(tokens[-1])
        or _SIMPLE_NUMERIC.match(tokens[-1])
    ):
        tokens.pop()

    if not tokens:
        return re.sub(r"\s+", " ", item_name.strip().lower())
    return " ".join(tokens)


def canonical_item_display_name(item_name: str) -> str:
    """Build a readable item name from canonical identity."""
    canonical = normalize_item_name(item_name)
    if not canonical:
        return item_name.strip()
    return " ".join(token.capitalize() for token in canonical.split())
