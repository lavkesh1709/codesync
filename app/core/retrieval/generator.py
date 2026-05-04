import time

import httpx
import structlog

from app.config import settings
from app.db.models import Chunk

log = structlog.get_logger()

# The prompt template — the LLM sees this every request.
# ONLY use the provided context — prevents hallucination.
# Cite file and line number — forces grounded answers.
SYSTEM_PROMPT = """You are a codebase assistant. Answer questions about the
codebase using ONLY the code context provided below.

Rules:
- Only use information from the provided context
- Always cite the specific file and line numbers for every claim
- If the context does not contain enough information to answer, say so clearly
- Do not hallucinate function names, file paths, or behaviour not shown"""


def _build_context(chunks: list[Chunk]) -> str:
    """
    Format retrieved chunks into a readable context block
    for the LLM prompt. Each chunk is clearly delimited
    with its file path and line numbers.
    """
    parts = []
    for chunk in chunks:
        parts.append(
            f"--- File: {chunk.file_path}, "
            f"lines {chunk.start_line}-{chunk.end_line} ---\n"
            f"{chunk.content}"
        )
    return "\n\n".join(parts)


async def generate(
    question: str,
    chunks: list[Chunk],
) -> str:
    """
    Call the Groq API with the question and retrieved context.
    Returns the LLM's answer as a plain string.

    Uses httpx async client — never requests (sync).
    Raises ValueError if the API call fails.
    """
    if not chunks:
        return (
            "I could not find relevant code in the indexed repository "
            "to answer this question. Try rephrasing or check that the "
            "repository has been indexed."
        )

    context = _build_context(chunks)

    user_message = f"""Context from the codebase:

{context}

Question: {question}"""

    log.info("generation_started", question=question[:80])
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 1024,
                "temperature": 0.1,  # low temp = factual, consistent answers
            },
        )

    if response.status_code != 200:
        log.error(
            "groq_api_error",
            status_code=response.status_code,
            body=response.text[:200],
        )
        raise ValueError(
            f"Groq API returned {response.status_code}: {response.text[:200]}"
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    log.info(
        "generation_complete",
        duration_ms=duration_ms,
        prompt_tokens=data["usage"]["prompt_tokens"],
        completion_tokens=data["usage"]["completion_tokens"],
    )

    return answer