"""Text normalisation, redaction and prompt-injection heuristics."""

from __future__ import annotations

import hashlib
import re
import unicodedata

# Patterns that indicate the customer text is trying to steer the model rather
# than describe an insurance situation. This is a *signal*, not a filter: the
# real defence is that customer text is always delimited and never trusted as
# instructions, and that no tool has read access to other customers' rows.
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+|your\s+|previous\s+|the\s+)*instructions?",
        r"ignora\s+(todas\s+)?(tus\s+)?(las\s+)?instrucciones",
        r"olvida\s+(tus\s+|las\s+)?instrucciones",
        r"disregard\s+(the\s+|your\s+)?(above|previous|prior|system)",
        r"system\s+prompt",
        r"prompt\s+del\s+sistema",
        r"you\s+are\s+now\s+a",
        r"ahora\s+eres\s+un",
        r"act\s+as\s+(a\s+)?(developer|admin|root)",
        # Patterns are matched against accent-folded text, so they are written
        # without accents. `\w*` covers Spanish enclitic pronouns ("muéstrame").
        r"(show|list|give|dame|muestra\w*|list\w*|envia\w*|facilita\w*)\s+.{0,40}\b"
        r"(other|otros?|todos los|demas)\s+(customer|client|cliente|usuari)",
        r"reveal\s+(your|the)\s+(prompt|instructions|rules)",
        r"database\s+(dump|schema)|select\s+\*\s+from",
        r"\bDAN\b\s+mode",
    )
)

# Best-effort PII masking for log lines. Data here is synthetic, but the code
# is written as though it were not.
_EMAIL_RE = re.compile(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s\-]{7,}\d)(?!\d)")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_PLATE_RE = re.compile(r"\b\d{4}\s?[A-Z]{3}\b")


def normalize_message(raw: str) -> str:
    """Clean inbound text without destroying meaning.

    Deliberately conservative: we collapse whitespace and strip control
    characters, but we keep accents, punctuation and emoji because they carry
    signal (an angry "!!!" matters for complaint detection).
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def detect_injection(text: str) -> list[str]:
    """Return the names of injection heuristics that fired.

    Accents are folded first so "Muéstrame" and "Muestrame" are treated the
    same - an attacker should not get through by typing correct Spanish.
    """
    if not text:
        return []
    folded = _fold_accents(text)
    return [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(folded)]


def redact(text: str, *, max_length: int = 200) -> str:
    """Mask obvious identifiers so message bodies are safe(r) to log."""
    if not text:
        return ""
    masked = _EMAIL_RE.sub("[email]", text)
    masked = _IBAN_RE.sub("[iban]", masked)
    masked = _PHONE_RE.sub("[phone]", masked)
    masked = _PLATE_RE.sub("[plate]", masked)
    if len(masked) > max_length:
        masked = masked[:max_length] + "…"
    return masked


def content_fingerprint(text: str) -> str:
    """Stable hash used for change detection and for logging without content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
