from __future__ import annotations

import structlog

from anyq.jobs.storage import SearchResult

log = structlog.get_logger()


class SearXNGClient:
    """Async SearXNG search client with proxy and User-Agent support."""

    ENGINES = "google,bing,duckduckgo"

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        proxy: str | None = None,
        user_agent: str | None = None,
    ) -> list[SearchResult]:
        try:
            import httpx

            headers = {}
            if user_agent:
                headers["User-Agent"] = user_agent

            transport = None
            if proxy:
                transport = httpx.AsyncHTTPTransport(proxy=proxy)

            async with httpx.AsyncClient(
                transport=transport,
                headers=headers,
                timeout=20.0,
                follow_redirects=True,
            ) as client:
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

            log.debug("searxng.results", query=query[:50], count=len(results))
            return results

        except Exception as exc:
            log.warning("searxng.search.failed", query=query[:50], error=str(exc))
            return []
