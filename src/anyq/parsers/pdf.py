from __future__ import annotations

import statistics

import structlog

from anyq.parsers.base import ParsedDocumentData

log = structlog.get_logger()


class PDFParser:
    """Parse PDF files using PyMuPDF (fitz).

    Heading detection strategy: collect all text spans with their font sizes,
    compute the median font size, then treat lines whose max span font size
    exceeds (median * threshold) as headings.
    """

    HEADING_FONT_RATIO = 1.2   # font size > median * ratio → heading
    MIN_HEADING_LEN = 3
    MAX_HEADING_LEN = 200

    def parse(self, content: bytes, filename: str) -> ParsedDocumentData:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=content, filetype="pdf")
        try:
            return self._extract(doc, filename)
        finally:
            doc.close()

    def _extract(self, doc: "fitz.Document", filename: str) -> ParsedDocumentData:
        import fitz

        metadata: dict[str, str] = {}
        raw_meta = doc.metadata or {}
        for key in ("title", "author", "subject", "creator", "producer"):
            value = raw_meta.get(key, "")
            if value:
                metadata[key] = value

        # --- Gather all text blocks with font size info ---
        all_lines: list[tuple[str, float]] = []   # (text, max_font_size)
        plain_lines: list[str] = []

        for page in doc:
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block.get("type") != 0:  # skip images
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    line_text = "".join(s["text"] for s in spans).strip()
                    if not line_text:
                        continue
                    max_size = max(s.get("size", 0.0) for s in spans)
                    all_lines.append((line_text, max_size))
                    plain_lines.append(line_text)

        # --- Determine median font size ---
        sizes = [sz for _, sz in all_lines if sz > 0]
        median_size = statistics.median(sizes) if sizes else 12.0

        # --- Extract headings ---
        headings: list[str] = []
        seen_headings: set[str] = set()
        for text, size in all_lines:
            if (
                size > median_size * self.HEADING_FONT_RATIO
                and self.MIN_HEADING_LEN <= len(text) <= self.MAX_HEADING_LEN
                and text not in seen_headings
            ):
                headings.append(text)
                seen_headings.add(text)

        # --- Title: metadata or first non-empty line ---
        title: str | None = metadata.get("title") or None
        if not title and plain_lines:
            title = plain_lines[0][:200]

        full_text = "\n".join(plain_lines)

        log.debug(
            "pdf.parsed",
            filename=filename,
            pages=doc.page_count,
            headings=len(headings),
            text_len=len(full_text),
        )

        return ParsedDocumentData(
            title=title,
            headings=headings,
            full_text=full_text,
            metadata=metadata,
        )
