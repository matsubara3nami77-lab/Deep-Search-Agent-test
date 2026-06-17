import asyncio
import os

from tavily import TavilyClient


async def search_web(query: str) -> list[dict]:
    """Search the web using Tavily and return structured results."""

    def _search() -> list[dict]:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        response = client.search(
            query=query,
            max_results=5,
            include_raw_content=False,
        )
        return response.get("results", [])

    return await asyncio.to_thread(_search)
