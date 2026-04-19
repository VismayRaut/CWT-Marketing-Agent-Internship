"""
report_agent.py
---------------
ReportAgent

Takes competitor data + company information and generates a structured
Markdown competitor-analysis report.

Input  : competitors (list[dict]), company_url (str), company_context (str)
Output : markdown string (the full report)
"""

import logging
import json
from typing import List, Dict, Any

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior market strategy consultant with deep expertise
in fintech and trading platforms.

Your task is to produce a **professional competitor analysis report** in Markdown.

The report must contain these sections (use the exact headings):

## 1. Executive Summary
(3-4 sentences capturing the key takeaway)

## 2. Market Overview
(Market size, growth trends, key dynamics in trading signals / prediction markets)

## 3. Competitor Comparison Table
(A Markdown table with columns: Competitor | Category | Core Offering | Key Strength | Key Weakness)

## 4. Detailed Competitor Profiles
(For each competitor: ### <Name>  then bullet points covering what they do, pricing model,
target audience, and main threat to CrowdWisdomTrading)

## 5. CrowdWisdomTrading's Differentiation Points
(Minimum 5 bullet points where CWT stands out vs the field)

## 6. Strategic Recommendations
(3-5 actionable recommendations for CWT based on the competitive landscape)

## 7. Conclusion

Write in a professional but clear tone. Use Markdown formatting throughout.
"""


class ReportAgent:
    """
    Generates a structured Markdown competitor analysis report.

    Parameters
    ----------
    llm : LLMClient
        Shared LLM client instance.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm
        logger.info("ReportAgent initialised.")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        competitors: List[Dict[str, Any]],
        company_url: str,
        company_context: str = "",
    ) -> str:
        """
        Generate the competitor analysis report.

        Parameters
        ----------
        competitors     : list[dict]  – output of CompetitorResearchAgent
        company_url     : str
        company_context : str

        Returns
        -------
        str  – full Markdown report
        """
        logger.info("ReportAgent.run() – %d competitors", len(competitors))

        user_prompt = self._build_prompt(competitors, company_url, company_context)
        report = self.llm.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=4096,
        )

        logger.info("Report generated (%d chars).", len(report))
        return report

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        competitors: List[Dict[str, Any]],
        company_url: str,
        company_context: str,
    ) -> str:
        ctx = company_context or (
            "CrowdWisdom Trading (https://www.crowdwisdomtrading.com/) aggregates "
            "insights from 2,086+ professional traders to deliver weekly AI-powered "
            "trade signals (entries, stop-loss, target levels). It boasts a ~73.3% "
            "tracked success rate and saves traders 100+ hours of research weekly. "
            "It targets active retail traders, short on time, who value collective "
            "intelligence over single analyst opinions."
        )

        competitors_json = json.dumps(competitors, indent=2)

        return (
            f"Company: {company_url}\n\n"
            f"Company Context:\n{ctx}\n\n"
            f"Competitors (JSON):\n{competitors_json}\n\n"
            "Please produce the full competitor analysis report for CrowdWisdomTrading "
            "based on the data above. Be specific, data-informed, and actionable."
        )
