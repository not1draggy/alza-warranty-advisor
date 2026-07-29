"""Input guard: prompt-injection defence and evidence sanitisation.

Two distinct jobs:

* `validate_query` rejects user input that is trying to steer the model instead of
  naming a product. Product names are short and boring; anything that reads like an
  instruction is not a product name.
* `sanitise_evidence` neutralises instruction-shaped text inside retrieved web pages
  before it reaches a prompt. Retrieved content is always untrusted.
"""

import re
import unicodedata

from app.core.errors import UnsafeInput

MAX_QUERY_LENGTH = 200

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\b",
        r"\bdisregard\s+(all\s+|any\s+)?(previous|prior|above|the)\b",
        r"\b(system|developer)\s+prompt\b",
        r"\bprompt\s+injection\b",
        r"\byou\s+are\s+now\b",
        r"\bact\s+as\s+(a|an)\b",
        r"\bpretend\s+(to\s+be|you)\b",
        r"\breveal\s+(your|the)\s+(instructions|prompt|rules)\b",
        r"\bprint\s+(your|the)\s+(instructions|prompt|system)\b",
        r"\bnew\s+instructions?\s*:",
        r"</?\s*(system|assistant|instructions?)\s*>",
        r"\bBEGIN\s+SYSTEM\b",
    )
)

# Structural markers that would let retrieved text impersonate a prompt section.
_STRUCTURAL_MARKERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"</?\s*(system|assistant|user|instructions?|evidence|human)\s*>",
        r"^\s*(system|assistant|human)\s*:",
    )
)

_SQL_PATTERNS = re.compile(
    r"(--|;\s*drop\s+table|\bunion\s+select\b|\bor\s+1\s*=\s*1\b)", re.IGNORECASE
)

_CONTROL_CHARS = {"Cc", "Cf", "Co", "Cs"}


def _strip_control_characters(text: str) -> str:
    return "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in _CONTROL_CHARS
    )


def validate_query(raw: str) -> str:
    """Normalise and vet a product query. Raises `UnsafeInput` when it looks hostile."""
    text = _strip_control_characters(unicodedata.normalize("NFKC", raw)).strip()
    text = " ".join(text.split())

    if not text:
        raise UnsafeInput("Zadajte názov produktu alebo číslo modelu.")
    if len(text) > MAX_QUERY_LENGTH:
        raise UnsafeInput(f"Názov produktu môže mať najviac {MAX_QUERY_LENGTH} znakov.")

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise UnsafeInput(
                "Toto nevyzerá ako názov produktu. Zadajte názov produktu alebo číslo modelu."
            )
    if _SQL_PATTERNS.search(text):
        raise UnsafeInput(
            "Toto nevyzerá ako názov produktu. Zadajte názov produktu alebo číslo modelu."
        )
    return text


def sanitise_evidence(text: str, *, max_chars: int = 4000) -> str:
    """Make retrieved text safe to embed in a prompt as data."""
    cleaned = _strip_control_characters(text)
    for pattern in _STRUCTURAL_MARKERS:
        cleaned = pattern.sub(" ", cleaned)
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[redacted directive]", cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + " …"
    return cleaned


def escape_for_display(text: str) -> str:
    """Strip characters that could break out of a text node when rendered."""
    return _strip_control_characters(text).replace("<", "&lt;").replace(">", "&gt;")
