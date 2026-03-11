from __future__ import annotations

import asyncio
import itertools

import structlog

log = structlog.get_logger()

_PROXYSCRAPE_URL = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies&protocol=http&timeout=5000"
    "&country=all&ssl=all&anonymity=all&format=json"
)


class ProxyPool:
    """Round-robin pool of Tor SOCKS5 proxies + free HTTP proxies."""

    def __init__(self, tor_hosts: list[str]) -> None:
        # tor_hosts: ["tor-1:9050", "tor-2:9050", ...]
        self._tor: list[str] = [f"socks5://{h}" for h in tor_hosts]
        self._free: list[str] = []
        self._cycle: itertools.cycle[str] | None = None
        self._rebuild_cycle()
        self._lock = asyncio.Lock()

    def _rebuild_cycle(self) -> None:
        pool = self._tor + self._free
        if pool:
            self._cycle = itertools.cycle(pool)
        else:
            self._cycle = None

    def get_next(self) -> str | None:
        if self._cycle is None:
            return None
        return next(self._cycle)

    async def refresh_free_proxies(self) -> None:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_PROXYSCRAPE_URL)
                resp.raise_for_status()
                data = resp.json()

            proxies = data.get("proxies", [])
            alive = [
                f"http://{p['ip']}:{p['port']}"
                for p in proxies
                if p.get("alive") and p.get("ip") and p.get("port")
            ]

            async with self._lock:
                self._free = alive[:50]  # keep top 50
                self._rebuild_cycle()

            log.info("proxy_pool.refreshed", free_count=len(self._free))

        except Exception as exc:
            log.warning("proxy_pool.refresh_failed", error=str(exc))

    async def start_refresh_loop(self, interval: int = 1800) -> None:
        while True:
            await self.refresh_free_proxies()
            await asyncio.sleep(interval)
