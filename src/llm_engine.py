import asyncio
import json
import logging
import os
import random
from typing import Any, Dict, Optional
import aiohttp

logger = logging.getLogger("LLMEngine")


class MultiTierLLMEngine:
    """Multi-Tier LLM extraction fallback engine:

    Gemini Flash -> Groq Llama 3 -> DeepSeek Handles 413 Payload Too Large
    (semantic truncation) and 429 Rate Limits.
    """

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    def _truncate_payload(self, text: str, max_chars: int = 12000) -> str:
        """Intelligently truncates text to avoid 413 Context Window Overflow while

        retaining high-density introductory and structural content.
        """
        if len(text) <= max_chars:
            return text
        head = text[: int(max_chars * 0.7)]
        tail = text[-int(max_chars * 0.3) :]
        return f"{head}\n\n[...TRUNCATED_TO_PREVENT_413...]\n\n{tail}"

    async def _execute_with_backoff(
        self, func, *args, max_retries: int = 4, base_delay: float = 1.5, **kwargs
    ):
        """Exponential backoff with full jitter for handling 429 & transient 5xx."""
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = (
                    "429" in err_str
                    or "rate" in err_str
                    or "quota" in err_str
                    or "resource_exhausted" in err_str
                )
                if attempt == max_retries - 1:
                    logger.error(
                        f"Final attempt failed for {func.__name__}: {e}"
                    )
                    raise e
                sleep_time = (base_delay * (2**attempt)) + random.uniform(
                    0.1, 1.0
                )
                logger.warning(
                    f"Attempt {attempt+1} failed with ({e}). Retrying in {sleep_time:.2f}s..."
                )
                await asyncio.sleep(sleep_time)

    async def _call_gemini(
        self, prompt: str, schema_instruction: str
    ) -> Optional[Dict[str, Any]]:
        """Tier 1: Gemini Flash."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"{schema_instruction}\n\nInput Content:\n{prompt}"}
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=20
            ) as resp:
                if resp.status == 429:
                    raise Exception("429 Too Many Requests from Gemini")
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Gemini API Error HTTP {resp.status}: {text}")
                data = await resp.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(content)

    async def _call_groq(
        self, prompt: str, schema_instruction: str
    ) -> Optional[Dict[str, Any]]:
        """Tier 2: Groq Llama 3."""
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a strict data extraction parser. Return ONLY valid JSON matching this schema: {schema_instruction}. Do not hallucinate. Keep unknown values as null.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=20
            ) as resp:
                if resp.status == 429:
                    raise Exception("429 Too Many Requests from Groq")
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Groq API Error HTTP {resp.status}: {text}")
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)

    async def _call_deepseek(
        self, prompt: str, schema_instruction: str
    ) -> Optional[Dict[str, Any]]:
        """Tier 3: DeepSeek."""
        if not self.deepseek_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured.")

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": f"Extract the canonical JSON according to: {schema_instruction}. Output valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=20
            ) as resp:
                if resp.status == 429:
                    raise Exception("429 Too Many Requests from DeepSeek")
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(
                        f"DeepSeek API Error HTTP {resp.status}: {text}"
                    )
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)

    async def extract_structured_data(
        self, raw_text: str, schema_instruction: str
    ) -> Dict[str, Any]:
        """Executes fallback chain across providers with intelligent 413 chunking."""
        safe_text = self._truncate_payload(raw_text)

        # Tier 1: Gemini Flash
        try:
            return await self._execute_with_backoff(
                self._call_gemini, safe_text, schema_instruction
            )
        except Exception as e:
            logger.warning(f"Tier 1 (Gemini Flash) failed: {e}. Falling back to Groq...")

        # Tier 2: Groq Llama
        try:
            return await self._execute_with_backoff(
                self._call_groq, safe_text, schema_instruction
            )
        except Exception as e:
            logger.warning(f"Tier 2 (Groq Llama) failed: {e}. Falling back to DeepSeek...")

        # Tier 3: DeepSeek
        try:
            return await self._execute_with_backoff(
                self._call_deepseek, safe_text, schema_instruction
            )
        except Exception as e:
            logger.critical(f"All LLM tiers failed. Last error: {e}")
            raise RuntimeError(f"Multi-tier LLM extraction completely exhausted: {e}")