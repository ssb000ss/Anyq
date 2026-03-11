from __future__ import annotations

# Proxy rotation is handled by SearXNG outgoing configuration (settings.yml).
# SearXNG routes its requests to Google/Bing/DDG through Tor SOCKS5 proxies
# defined in outgoing.proxies. No application-level proxy management needed.
#
# This module is kept as a placeholder for future use (e.g. per-request
# circuit rotation via Tor control port).
