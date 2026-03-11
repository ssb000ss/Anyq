from __future__ import annotations

import asyncio
import random

import structlog

from anyq.jobs.storage import SearchResult
from anyq.search.proxy_pool import ProxyPool
from anyq.search.searxng import SearXNGClient
from anyq.search.ua_pool import get_random_ua

log = structlog.get_logger()


class SearchOrchestrator:
    """Execute multiple search queries with proxy and UA rotation."""

    def __init__(
        self,
        proxy_pool: ProxyPool,
        searxng: SearXNGClient,
        delay_min: float = 1.5,
        delay_max: float = 4.0,
    ) -> None:
        self._proxy_pool = proxy_pool
        self._searxng = searxng
        self._delay_min = delay_min
        self._delay_max = delay_max

    async def search_all(
        self,
        queries: list[str],
        on_progress: "asyncio.coroutines.CoroType | None" = None,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        total = len(queries)

        for idx, query in enumerate(queries, start=1):
            proxy = self._proxy_pool.get_next()
            ua = get_random_ua()

            log.info(
                "search.query",
                idx=idx,
                total=total,
                query=query[:60],
                proxy=proxy,
            )

            await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))

            batch = await self._searxng.search(query, proxy=proxy, user_agent=ua)

            for result in batch:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    results.append(result)

            if on_progress:
                await on_progress(idx, total)

        log.info("search.done", total_unique=len(results))
        return results
