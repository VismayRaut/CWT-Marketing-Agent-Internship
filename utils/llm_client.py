"""
llm_client.py
-------------
Thin wrapper around the OpenRouter API (OpenAI-compatible).
Supports chat completions with retry logic and system/user message construction.
"""

import os
import time
import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default free model on OpenRouter
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS_TEMPLATE = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://www.crowdwisdomtrading.com/",
    "X-Title": "CrowdWisdomTrading Marketing Intelligence",
}


class LLMClient:
    """
    OpenRouter chat-completion client.

    Parameters
    ----------
    api_key : str, optional
        OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
    model : str, optional
        Model identifier (default: mistral-7b-instruct free tier).
    max_retries : int
        Number of retry attempts on transient errors.
    retry_delay : float
        Seconds to wait between retries.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 5,
        retry_delay: float = 5.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. "
                "Set OPENROUTER_API_KEY environment variable or pass api_key."
            )
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info("LLMClient initialised with model: %s", self.model)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Send a list of messages to OpenRouter and return the assistant reply text.

        Parameters
        ----------
        messages : list of {"role": ..., "content": ...}
        temperature : float
        max_tokens : int

        Returns
        -------
        str  – the assistant's reply text
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {**HEADERS_TEMPLATE, "Authorization": f"Bearer {self.api_key}"}

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("LLM request attempt %d/%d", attempt, self.max_retries)
                response = requests.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                reply = data["choices"][0]["message"]["content"].strip()
                logger.debug("LLM response received (%d chars)", len(reply))
                return reply

            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else "N/A"
                logger.warning("HTTP %s on attempt %d: %s", status, attempt, exc)
                if attempt == self.max_retries:
                    raise
            except requests.exceptions.RequestException as exc:
                logger.warning("Request error on attempt %d: %s", attempt, exc)
                if attempt == self.max_retries:
                    raise
            except (KeyError, IndexError) as exc:
                logger.error("Unexpected response structure: %s", exc)
                raise

            time.sleep(self.retry_delay * attempt)

        raise RuntimeError("LLM request failed after all retries")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Convenience wrapper: builds a [system, user] message list and calls chat().

        Parameters
        ----------
        system_prompt : str
        user_prompt   : str

        Returns
        -------
        str
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)
