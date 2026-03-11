from __future__ import annotations

from anyq.parsers.base import ParsedDocumentData


class RuleBasedQueryGenerator:
    """Generate search queries from document structure without LLM."""

    def generate(
        self,
        doc: ParsedDocumentData,
        key_phrases: list[str],
        samples: list[str],
        max_queries: int = 15,
    ) -> list[str]:
        queries: list[str] = []

        if doc.title:
            title = doc.title.strip()
            queries.append(f'"{title}" filetype:pdf')
            queries.append(f'"{title}"')

        for heading in doc.headings[:4]:
            h = heading.strip()
            if len(h) > 5:
                queries.append(f'"{h}"')

        for phrase in key_phrases[:5]:
            p = phrase.strip()
            if len(p) > 10:
                queries.append(f'"{p}"')

        for sentence in samples[:3]:
            chunk = sentence.strip()[:120]
            if len(chunk) > 20:
                queries.append(f'"{chunk}"')

        # deduplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)

        return unique[:max_queries]
