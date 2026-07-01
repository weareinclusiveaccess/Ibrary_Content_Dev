"""Helpers for reading curriculum–textbook alignment JSON."""


def alignment_matches(alignment: dict, unit_id: str) -> list[dict]:
    """Resolve chunk matches for a unit from alignment JSON (new or legacy format)."""
    entry = alignment.get(unit_id)
    if entry is None:
        return []
    if isinstance(entry, list):
        return entry
    if isinstance(entry, dict):
        m = entry.get("matches")
        if isinstance(m, list):
            return m
    return []
