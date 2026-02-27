from __future__ import annotations

import logging
import re

import httpx

from agent.activity_log import log_tool_call

logger = logging.getLogger(__name__)

SEARCH_URL = "https://html.duckduckgo.com/html/"
TIMEOUT = 15


async def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return top results.

    Args:
        query: The search query string.
    """
    with log_tool_call("web_search", query) as tool_log:
        logger.info("Tool web_search: %s", query)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.post(
                    SEARCH_URL,
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; ShketAgent/1.0)"},
                )
                resp.raise_for_status()
                result = _parse_results(resp.text)
                # Count results
                count = len(result.split("\n\n")) if result != "No results found." else 0
                tool_log.log_result(f"{count} results")
                return result
        except Exception as e:
            logger.error("web_search failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Search error: {e}"


def _parse_results(html: str) -> str:
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        url = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if title:
            results.append(f"- {title}\n  {url}\n  {snippet}")
        if len(results) >= 5:
            break
    return "\n\n".join(results) if results else "No results found."
