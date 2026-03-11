from __future__ import annotations

import structlog

from anyq.parsers.base import ParsedDocumentData

log = structlog.get_logger()


class DOCXParser:
    """Parse DOCX files using python-docx."""

    HEADING_STYLES = {"Heading 1", "Heading 2", "Heading 3", "Heading 4"}

    def parse(self, content: bytes, filename: str) -> ParsedDocumentData:
        import io

        from docx import Document

        doc = Document(io.BytesIO(content))
        return self._extract(doc, filename)

    def _extract(self, doc: "Document", filename: str) -> ParsedDocumentData:
        metadata: dict[str, str] = {}
        props = doc.core_properties
        if props.title:
            metadata["title"] = props.title
        if props.author:
            metadata["author"] = props.author
        if props.subject:
            metadata["subject"] = props.subject

        headings: list[str] = []
        all_paragraphs: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            all_paragraphs.append(text)
            if para.style and para.style.name in self.HEADING_STYLES:
                headings.append(text)

        title: str | None = metadata.get("title") or None
        if not title and all_paragraphs:
            title = all_paragraphs[0][:200]

        full_text = "\n".join(all_paragraphs)

        log.debug(
            "docx.parsed",
            filename=filename,
            headings=len(headings),
            text_len=len(full_text),
        )

        return ParsedDocumentData(
            title=title,
            headings=headings,
            full_text=full_text,
            metadata=metadata,
        )
