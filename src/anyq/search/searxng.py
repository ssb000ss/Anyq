from __future__ import annotations

import httpx
import structlog

from anyq.jobs.storage import SearchResult

log = structlog.get_logger()


class SearXNGClient:
    """Async SearXNG search client.

    SearXNG handles proxy rotation (Tor outgoing) via its own settings.yml.
    This client simply sends queries to the local SearXNG instance.
    """

    ENGINES = "google,bing,duckduckgo"

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": self.ENGINES,
                        "language": "ru-RU",
                        "safesearch": "0",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            for item in data.get("results", []):
                url = item.get("url", "")
                title = item.get("title", "")
                snippet = item.get("content", "") or item.get("snippet", "")
                engine = item.get("engine", "unknown")
                if url and title:
                    results.append(
                        SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            query=query,
                            engine=engine,
                        )
                    )

            log.debug("searxng.results", query=query[:60], count=len(results))
            return results

        except Exception as exc:
            log.warning("searxng.search.failed", query=query[:60], error=str(exc))
            return []
