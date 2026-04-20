"""
competitor_agent.py
--------------------
CompetitorResearchAgent

Identifies direct and indirect competitors of a given company URL using
an LLM, enriching the analysis with known contextual data about the
prediction-market / trading-signal niche.

Input  : company URL (str)
Output : list of dicts with keys  { name, url, description, category }
"""

import logging
import json
import re
from typing import List, Dict, Any

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert business intelligence analyst specialising in
fintech, trading platforms, and prediction markets.

Your task is to identify competitors for a given company. Be thorough and include:
1. Direct competitors offering the same or very similar product.
2. Indirect competitors that solve the same underlying problem differently.
3. Emerging / niche players the company must watch.

For each competitor, provide:
- name       : Company / product name
- url        : Official website URL
- description: 2-3 sentence description of what they do and how they compete
- category   : "direct" | "indirect" | "emerging"

Return ONLY a valid JSON array of objects with those four keys. No prose, no markdown fences.
"""


class CompetitorResearchAgent:
    """
    Queries an LLM to identify competitors for a given company.

    Parameters
    ----------
    llm : LLMClient
        Shared LLM client instance.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm
        logger.info("CompetitorResearchAgent initialised.")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, company_url: str, company_context: str = "") -> List[Dict[str, Any]]:
        """
        Identify competitors for *company_url*.

        Parameters
        ----------
        company_url     : str  – e.g. "https://www.crowdwisdomtrading.com/"
        company_context : str  – optional additional description of the company

        Returns
        -------
        list[dict]  – competitor objects
        """
        logger.info("CompetitorResearchAgent.run() -> %s", company_url)

        user_prompt = self._build_prompt(company_url, company_context)
        raw = self.llm.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=2048,
        )

        competitors = self._parse_response(raw)
        logger.info("Found %d competitors.", len(competitors))
        return competitors

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_prompt(self, company_url: str, company_context: str) -> str:
        ctx = company_context or (
            "CrowdWisdom Trading aggregates insights from 2,000+ professional traders "
            "to deliver weekly AI-powered trade signals (entries, stop-loss, targets). "
            "It targets active retail traders who want collective intelligence rather "
            "than single-analyst opinions. It competes in the trading signal / "
            "prediction market / market intelligence niche."
        )
        return (
            f"Company URL: {company_url}\n\n"
            f"Company Context:\n{ctx}\n\n"
            "List all notable competitors in this niche (aim for 8-12 competitors). "
            "Include well-known names such as TipRanks, Seeking Alpha, Investing.com, "
            "Motley Fool, Trade Ideas, Kalshi, Polymarket, and any others relevant to "
            "trading signals, crowd-sourced financial intelligence, or prediction markets."
        )

    @staticmethod
    def _parse_response(raw: str) -> List[Dict[str, Any]]:
        """
        Extract JSON array from the LLM response, even if there is surrounding text.
        """
        # Strip markdown code fences if present
        clean = re.sub(r"```(?:json)?", "", raw).strip()

        # Find the first '[' … ']' block
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.error("No JSON array found in LLM response:\n%s", raw[:500])
            return []

        json_str = clean[start : end + 1]
        try:
            competitors = json.loads(json_str)
            DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
            validated = []
            for item in competitors:
                if isinstance(item, dict) and "name" in item:
                    validated.append(
                        {
                            "name": item.get("name", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                            "category": item.get("category", "direct"),
                        }
                    )
            return validated
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s\nRaw: %s", exc, json_str[:300])
            return []
