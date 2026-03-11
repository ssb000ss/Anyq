from __future__ import annotations

from typing import Protocol, runtime_checkable


class ParsedDocument(Protocol):
    title: str | None
    headings: list[str]
    full_text: str
    metadata: dict[str, str]


@runtime_checkable
class DocumentParser(Protocol):
    def parse(self, content: bytes, filename: str) -> "ParsedDocumentData":
        ...


class ParsedDocumentData:
    """Concrete implementation of ParsedDocument used by all parsers."""

    __slots__ = ("title", "headings", "full_text", "metadata")

    def __init__(
        self,
        title: str | None,
        headings: list[str],
        full_text: str,
        metadata: dict[str, str],
    ) -> None:
        self.title = title
        self.headings = headings
        self.full_text = full_text
        self.metadata = metadata

    def __repr__(self) -> str:
        return (
            f"ParsedDocumentData(title={self.title!r}, "
            f"headings={len(self.headings)}, "
            f"text_len={len(self.full_text)})"
        )
