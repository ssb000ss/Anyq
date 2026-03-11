from __future__ import annotations

import re

import structlog

from anyq.parsers.base import ParsedDocumentData

log = structlog.get_logger()

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "latin-1")
_HEADING_RE = re.compile(r"^(#{1,4}\s+.+|[A-ZА-ЯЁ\s]{5,80})$")


def _decode(content: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", errors="replace")


class TXTParser:
    """Parse plain text files with encoding auto-detection."""

    def parse(self, content: bytes, filename: str) -> ParsedDocumentData:
        text = _decode(content)
        lines = [line.rstrip() for line in text.splitlines()]
        non_empty = [line for line in lines if line.strip()]

        headings: list[str] = []
        for line in non_empty:
            stripped = line.strip()
            if _HEADING_RE.match(stripped) and len(stripped) >= 5:
                clean = stripped.lstrip("#").strip()
                if clean:
                    headings.append(clean)

        title: str | None = non_empty[0].strip()[:200] if non_empty else None

        log.debug(
            "txt.parsed",
            filename=filename,
            headings=len(headings),
            text_len=len(text),
        )

        return ParsedDocumentData(
            title=title,
            headings=headings,
            full_text=text,
            metadata={},
        )
