from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import structlog

from anyq.jobs.storage import SearchResult
from anyq.search.searxng import SearXNGClient

log = structlog.get_logger()


class SearchOrchestrator:
    """Execute multiple search queries with anti-ban delays.

    Proxy rotation is handled by SearXNG outgoing config (Tor).
    This orchestrator only controls request pacing.
    """

    def __init__(
        self,
        searxng: SearXNGClient,
        delay_min: float = 1.5,
        delay_max: float = 4.0,
    ) -> None:
        self._searxng = searxng
        self._delay_min = delay_min
        self._delay_max = delay_max

    async def search_all(
        self,
        queries: list[str],
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        total = len(queries)

        for idx, query in enumerate(queries, start=1):
            log.info("search.query", idx=idx, total=total, query=query[:60])

            await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))

            batch = await self._searxng.search(query)

            for result in batch:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    results.append(result)

            if on_progress:
                await on_progress(idx, total)

        log.info("search.done", total_unique=len(results))
        return results
