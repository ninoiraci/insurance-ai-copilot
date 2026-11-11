"""Markdown-aware chunking.

Design decision: chunk on **section boundaries first**, then split oversized
sections on paragraph boundaries. Insurance procedure documents are structured
("3. Documentación obligatoria"), and that structure is exactly what makes a
citation useful to an operator. A fixed-size sliding window would produce
chunks that cite "section ?" and cut requirement lists in half.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    content: str
    index: int
    section: str
    metadata: dict


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(section_title, body)] preserving document order."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("full document", text.strip())]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("introduction", preamble))

    for position, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))
    return sections


def _split_long_body(body: str, target: int, overlap: int) -> list[str]:
    """Split on paragraphs, keeping a small overlap for context continuity."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    pieces: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= target:
            current = f"{current}\n\n{paragraph}"
        else:
            pieces.append(current)
            tail = current[-overlap:] if overlap and len(current) > overlap else ""
            current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    if current:
        pieces.append(current)

    # A single paragraph longer than the target still needs hard splitting.
    final: list[str] = []
    for piece in pieces:
        while len(piece) > target * 2:
            cut = piece.rfind(". ", 0, target * 2)
            cut = cut + 1 if cut > target // 2 else target * 2
            final.append(piece[:cut].strip())
            piece = piece[max(0, cut - overlap) :].strip()
        if piece:
            final.append(piece)
    return final


def chunk_document(
    text: str,
    *,
    title: str,
    target_chars: int = 900,
    overlap_chars: int = 150,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section_title, body in _split_sections(text):
        # The H1 usually repeats the document title; citing "Title, Title"
        # reads like a bug to an operator.
        if section_title.strip().lower() == title.strip().lower():
            section_title = "introducción"
        for part in _split_long_body(body, target_chars, overlap_chars):
            # Prefixing the heading keeps the chunk self-describing, which
            # measurably improves retrieval for short queries.
            content = f"{section_title}\n{part}".strip()
            chunks.append(
                Chunk(
                    content=content,
                    index=len(chunks),
                    section=section_title[:190],
                    metadata={
                        "document_title": title,
                        "section": section_title[:190],
                        "char_count": len(content),
                    },
                )
            )
    return chunks
