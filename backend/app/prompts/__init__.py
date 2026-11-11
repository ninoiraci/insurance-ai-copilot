"""Versioned prompt registry.

Prompts are Markdown files on disk, not string literals inside route handlers.
That gives them a diffable history, lets a reviewer read them without reading
Python, and makes `prompt_version` a meaningful column in `ai_analyses`.

Rendering uses explicit key replacement rather than `str.format` because the
prompt bodies contain JSON braces that `format` would choke on.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent

CLASSIFICATION_PROMPT = "classification_v1"
RESPONSE_PROMPT = "response_v1"
RAG_ANSWER_PROMPT = "rag_answer_v1"


class PromptNotFound(KeyError):
    pass


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    purpose: str
    system: str
    user: str

    def render(self, **values: object) -> tuple[str, str]:
        """Return (system, user) with `{placeholder}` tokens substituted."""
        system, user = self.system, self.user
        for key, value in values.items():
            token = "{" + key + "}"
            replacement = "" if value is None else str(value)
            system = system.replace(token, replacement)
            user = user.replace(token, replacement)
        return system.strip(), user.strip()


def _parse(raw: str, name: str) -> PromptTemplate:
    version, purpose = name, ""
    body = raw

    if raw.startswith("---"):
        _, frontmatter, body = raw.split("---", 2)
        for line in frontmatter.strip().splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if key == "version":
                version = value
            elif key == "purpose":
                purpose = value

    system_part, user_part = body, ""
    if "\n# USER" in body:
        system_part, user_part = body.split("\n# USER", 1)
    system_part = system_part.replace("# SYSTEM", "", 1)

    return PromptTemplate(
        version=version,
        purpose=purpose,
        system=system_part.strip(),
        user=user_part.strip(),
    )


@lru_cache(maxsize=None)
def get_prompt(name: str) -> PromptTemplate:
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFound(f"prompt '{name}' not found in {PROMPT_DIR}")
    return _parse(path.read_text(encoding="utf-8"), name)


def list_prompts() -> list[PromptTemplate]:
    return [get_prompt(path.stem) for path in sorted(PROMPT_DIR.glob("*.md"))]


__all__ = [
    "CLASSIFICATION_PROMPT",
    "PromptNotFound",
    "PromptTemplate",
    "RAG_ANSWER_PROMPT",
    "RESPONSE_PROMPT",
    "get_prompt",
    "list_prompts",
]
