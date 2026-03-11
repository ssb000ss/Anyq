from __future__ import annotations

import structlog

from anyq.parsers.base import ParsedDocumentData

log = structlog.get_logger()

_PROMPT_TEMPLATE = """\
You are a search query expert. Given a document's title and key phrases, \
generate exactly 5 effective Google search queries to find this document or \
its source on the internet.

Rules:
- Each query on a separate line
- Use quotes around exact phrases
- Try different angles: title, author, topic, unique phrases
- No explanations, just queries

Document title: {title}
Key phrases: {phrases}

Generate 5 search queries:"""


class OllamaQueryGenerator:
    """Generate search queries using local Ollama LLM."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(
        self,
        doc: ParsedDocumentData,
        key_phrases: list[str],
    ) -> list[str]:
        if not doc.title and not key_phrases:
            return []

        try:
            import httpx

            prompt = _PROMPT_TEMPLATE.format(
                title=doc.title or "Unknown",
                phrases=", ".join(key_phrases[:8]),
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 300},
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("response", "")
            queries = self._parse_queries(raw)
            log.debug("ollama.queries", count=len(queries))
            return queries

        except Exception as exc:
            log.warning("ollama.generate.failed", error=str(exc))
            return []

    @staticmethod
    def _parse_queries(raw: str) -> list[str]:
        queries: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            # strip leading numbers/bullets like "1." "- " "* "
            line = line.lstrip("0123456789.-*)• ").strip()
            if len(line) > 5:
                queries.append(line)
        return queries[:5]
