"""DuckDuckGo web search tool (free, no API key)."""

from __future__ import annotations

from agentforge.tools.base import Tool


async def _web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return formatted results."""
    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            results = []
            async for r in ddgs.text(query, max_results=max_results):
                results.append(r)

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", r.get("link", "No URL"))
            snippet = r.get("body", r.get("snippet", "No description"))
            formatted.append(f"{i}. {title}\n   {url}\n   {snippet}")

        return "\n\n".join(formatted)

    except ImportError:
        # Fallback: use httpx to query DuckDuckGo HTML
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "AgentForge/0.1"},
                follow_redirects=True,
            )
            if resp.status_code == 200:
                # Simple extraction from HTML
                text = resp.text
                results_text = []
                count = 0
                for line in text.split("\n"):
                    if "result__a" in line and "href" in line:
                        count += 1
                        if count > max_results:
                            break
                        # Extract text between > and </a>
                        start = line.find(">") + 1
                        end = line.find("</a>")
                        if start > 0 and end > start:
                            title = line[start:end].strip()
                            results_text.append(f"{count}. {title}")
                return "\n".join(results_text) if results_text else f"No results found for: {query}"
            return f"Search failed with status {resp.status_code}"

    except Exception as e:
        return f"Search error: {e}"


web_search_tool = Tool(
    name="web_search",
    description=(
        "Search the web for current information. Use when you need "
        "up-to-date facts, data, or information about any topic."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    handler=_web_search,
)
