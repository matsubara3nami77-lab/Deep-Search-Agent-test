import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


async def generate_report(query: str, search_results: list[dict]) -> str:
    """Generate a structured research report using Gemini 2.5 Flash Lite."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.7,
    )

    context_parts: list[str] = []
    for i, result in enumerate(search_results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        content = result.get("content", "")
        context_parts.append(f"**[{i}] {title}**\nURL: {url}\n\n{content}")

    context = (
        "\n\n---\n\n".join(context_parts)
        if context_parts
        else "No search results were found."
    )

    prompt = f"""You are an expert research analyst. Create a comprehensive, well-structured research report based on the following web search results.

Research Topic: {query}

Web Search Results:
{context}

Write a professional research report in Markdown format. Structure it with:
- A descriptive title as an H1 heading
- ## Executive Summary (2–3 paragraphs summarising the key points)
- ## Key Findings (bullet points with the most important discoveries)
- ## Detailed Analysis (multiple H3 subsections diving deep into the topic)
- ## Conclusion
- ## References (numbered list with titles and URLs)

Be thorough, cite sources where relevant, and provide genuine analytical value."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return str(response.content)
