"""US/UK spelling locale checks.

A deliberately conservative, dependency-free checker. It only flags a curated
set of high-signal US<->UK spelling pairs (plus mechanically generated
inflections for the ``-ize/-ise`` and ``-or/-our`` families) so that it does not
produce noise on ambiguous words like "program"/"programme" or "meter"/"metre".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Base US -> UK spelling pairs (lowercase). Ambiguous words are intentionally
# excluded to avoid false positives.
_BASE_US_TO_UK: dict[str, str] = {
    "color": "colour",
    "colors": "colours",
    "colored": "coloured",
    "favor": "favour",
    "favors": "favours",
    "favorite": "favourite",
    "honor": "honour",
    "labor": "labour",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "neighbor": "neighbour",
    "neighbors": "neighbours",
    "center": "centre",
    "centers": "centres",
    "centered": "centred",
    "theater": "theatre",
    "fiber": "fibre",
    "defense": "defence",
    "offense": "offence",
    "catalog": "catalogue",
    "dialog": "dialogue",
    "gray": "grey",
    "modeling": "modelling",
    "modeled": "modelled",
    "labeled": "labelled",
    "labeling": "labelling",
    "traveled": "travelled",
    "traveling": "travelling",
    "canceled": "cancelled",
    "fulfill": "fulfil",
    "enrollment": "enrolment",
    "artifact": "artefact",
    "artifacts": "artefacts",
}

# Verbs whose US ``-ize`` maps to UK ``-ise`` (base stem, no suffix).
_IZE_STEMS = [
    "organ",
    "recogn",
    "emphas",
    "real",
    "analy",  # analyze/analyse (special-cased z->s below)
    "priorit",
    "util",
    "maxim",
    "minim",
    "optim",
    "summar",
    "categor",
    "special",
    "standard",
    "custom",
]


def _build_us_to_uk() -> dict[str, str]:
    mapping = dict(_BASE_US_TO_UK)
    for stem in _IZE_STEMS:
        # analyze is spelled with 'yze' -> 'yse'
        if stem == "analy":
            forms = {
                "analyze": "analyse",
                "analyzes": "analyses",
                "analyzed": "analysed",
                "analyzing": "analysing",
            }
            mapping.update(forms)
            continue
        for us_suffix, uk_suffix in (
            ("ize", "ise"),
            ("izes", "ises"),
            ("ized", "ised"),
            ("izing", "ising"),
            ("ization", "isation"),
        ):
            mapping[stem + us_suffix] = stem + uk_suffix
    return mapping


US_TO_UK: dict[str, str] = _build_us_to_uk()
UK_TO_US: dict[str, str] = {uk: us for us, uk in US_TO_UK.items()}


@dataclass
class SpellingHit:
    """A single spelling-locale mismatch."""

    word: str
    suggestion: str
    line_number: int


def check_spelling(text: str, locale: str) -> list[SpellingHit]:
    """Return spelling-locale mismatches in ``text`` for the given ``locale``.

    For ``en-GB`` it flags US spellings (suggesting the UK form); for ``en-US``
    it flags UK spellings. Any other locale yields no hits.
    """
    if locale == "en-GB":
        mapping: Optional[dict[str, str]] = US_TO_UK
    elif locale == "en-US":
        mapping = UK_TO_US
    else:
        return []

    hits: list[SpellingHit] = []
    seen: set[tuple[str, int]] = set()
    for line_number, line in enumerate(text.split("\n"), 1):
        for match in re.finditer(r"[A-Za-z]+", line):
            word = match.group(0)
            lower = word.lower()
            if lower in mapping:
                key = (lower, line_number)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(
                    SpellingHit(
                        word=word,
                        suggestion=mapping[lower],
                        line_number=line_number,
                    )
                )
    return hits
