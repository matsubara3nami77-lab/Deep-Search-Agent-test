import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.clarification_service import _parse_json_object
from app.services.gemini_service import _normalise_llm_content

ASSISTANT_DESCRIPTION = (
    "You are the built-in assistant for a Deep Research Agent web app. "
    "The app researches a topic using web search (Tavily) and Google Gemini, "
    "generates a structured markdown report shown in the right panel, and asks "
    "the user to approve saving it to disk (human-in-the-loop). "
    "It has two modes: TODO mode (runs research immediately) and PLAN mode "
    "(generates a step-by-step research plan for review/regeneration before running). "
    "Users can switch modes with the toggle or the /todo and /plan chat commands."
)


async def classify_intent(query: str) -> dict:
    """
    Decide whether a message is a research request or a conversational message
    (greeting, "who are you?", "how do I use this?", small talk, capability
    questions). For conversational messages, also produce a friendly reply.

    Returns:
        {"kind": "research"}
        or
        {"kind": "chat", "answer": "..."}

    On any failure it defaults to {"kind": "research"} so research is never blocked.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.3,
        max_retries=1,
    )

    prompt = f"""{ASSISTANT_DESCRIPTION}

Classify the user's message into exactly one of these kinds:
- "mode_switch": the user wants to change the workflow mode WITHOUT giving a research
  topic. Examples: "switch to plan mode", "let's plan first", "use planning mode",
  "go back to todo mode", "just research it directly", "/plan", "/todo".
  Determine the target: "plan" for planning, "todo" for direct/immediate research.
- "chat": conversational or meta messages (greetings like "hi"/"hello", "who are you?",
  "what can you do?", "how do I use this effectively?", thanks, small talk) that are
  NOT a research topic and NOT a mode change.
- "research": a topic, question, or subject the user wants researched.

User message: "{query}"

Rules:
- If the message names a concrete research topic, choose "research" even if it mentions
  a mode (the mode is handled separately by the UI toggle).
- Only choose "mode_switch" when the message is essentially just a request to change mode.
- For "chat", write a concise, friendly answer (1-4 sentences). When relevant, briefly
  explain what this agent does or how to use it (modes, commands, approval step).
- For "chat", NEVER claim that you switched, changed, or set a mode. You cannot change
  modes from a chat answer.
- For "mode_switch", write a short confirmation answer (e.g. "Switched to PLAN mode...").

Return ONLY one JSON object, one of:
{{"kind": "research"}}
{{"kind": "chat", "answer": "..."}}
{{"kind": "mode_switch", "target": "plan", "answer": "..."}}
{{"kind": "mode_switch", "target": "todo", "answer": "..."}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = _normalise_llm_content(response.content)
        data = _parse_json_object(text)
        if not data:
            return {"kind": "research"}

        kind = data.get("kind")
        if kind == "mode_switch":
            target = str(data.get("target", "")).strip().lower()
            if target in ("plan", "todo"):
                answer = str(data.get("answer", "")).strip()
                return {"kind": "mode_switch", "target": target, "answer": answer}
            return {"kind": "research"}

        if kind == "chat":
            answer = str(data.get("answer", "")).strip()
            if answer:
                return {"kind": "chat", "answer": answer}

        return {"kind": "research"}
    except Exception:
        return {"kind": "research"}
