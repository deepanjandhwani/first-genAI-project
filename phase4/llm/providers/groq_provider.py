"""
Groq LLM provider for Phase 4. Uses GROQ_API_KEY from environment or .env.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _load_env():
    """Load .env from project root so GROQ_API_KEY is available when server runs without dotenv."""
    try:
        from dotenv import load_dotenv
        # Project root: phase4/llm/providers/groq_provider.py -> ../../.. = project root
        env_path = Path(__file__).resolve().parents[3] / ".env"
        load_dotenv(env_path)
    except ImportError:
        pass


def _get_client():
    """Lazy import to avoid requiring groq when not using Phase 4."""
    _load_env()
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("Install groq: pip install groq")
    key = os.environ.get("GROQ_API_KEY")
    logger.info("Groq client: GROQ_API_KEY=%s", "set" if key else "NOT SET")
    if not key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to .env in the project root or set the environment variable."
        )
    return Groq(api_key=key)


def groq_chat_completion(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> tuple[str, Optional[int]]:
    """
    Call Groq chat completion. Returns (content, latency_ms).
    Raises on missing key or API error.
    """
    client = _get_client()
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    content = response.choices[0].message.content if response.choices else ""
    return (content or "", elapsed_ms)
