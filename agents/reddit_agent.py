"""
reddit_agent.py
---------------
RedditPainAgent

Uses Apify to scrape Reddit posts about prediction markets / trading problems,
then uses an LLM to extract structured pain points from the raw data.

Input  : (none – queries are hardcoded based on product niche)
Output : list of pain-point dicts
         { title, body_excerpt, subreddit, url, pain_summary, pain_category }
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional

from utils.llm_client import LLMClient
from utils.apify_client import ApifyClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reddit search queries (targeting CWT's niche)
# ---------------------------------------------------------------------------
REDDIT_QUERIES = [
    "prediction markets problems",
    "trading signals too many conflicting opinions",
    "stock market research overwhelming",
    "trading prediction issues wrong signals",
    "betting market complaints prediction accuracy",
    "how to find reliable stock picks reddit",
    "analyst recommendations useless",
]

# ---------------------------------------------------------------------------
# System prompt for pain-point extraction
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """You are an expert at identifying user pain points from
Reddit discussions related to trading, investment research, and prediction markets.

Given a batch of raw Reddit posts and comments, extract the genuine user pain points.

For each pain point return a JSON object with:
- title        : short title for the pain point (max 10 words)
- body_excerpt : most relevant verbatim quote from the post (max 60 words)
- subreddit    : the subreddit name (e.g. "investing")
- url          : post URL
- pain_summary : 1-2 sentence plain-English summary of the frustration
- pain_category: one of [ "signal_overload", "credibility", "time_cost",
                           "emotional_trading", "bad_prediction", "research_difficulty",
                           "other" ]

Focus on authentic frustrations that CrowdWisdomTrading's collective-intelligence
approach could plausibly solve.

Return ONLY a valid JSON array. No prose, no markdown fences.
"""


class RedditPainAgent:
    """
    Scrapes Reddit for pain points in the trading/prediction-market niche.

    Parameters
    ----------
    llm        : LLMClient
    apify      : ApifyClient
    max_posts  : int   – max posts to scrape per query (Apify limit)
    """

    def __init__(
        self,
        llm: LLMClient,
        apify: ApifyClient,
        max_posts: int = 10,
    ):
        self.llm = llm
        self.apify = apify
        self.max_posts = max_posts
        logger.info("RedditPainAgent initialised.")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        queries: Optional[List[str]] = None,
        past_pain_points: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrape Reddit and extract pain points.

        Parameters
        ----------
        queries          : custom search queries (defaults to REDDIT_QUERIES)
        past_pain_points : pain points stored by LearningAgent (for dedup)

        Returns
        -------
        list[dict]  – pain-point objects
        """
        queries = queries or REDDIT_QUERIES
        logger.info("RedditPainAgent.run() – %d queries", len(queries))

        # 1. Scrape
        raw_posts = self.apify.scrape_reddit(
            search_queries=queries,
            posts_per_query=self.max_posts,
            include_comments=True,
        )
        logger.info("Total raw Reddit items scraped: %d", len(raw_posts))

        if not raw_posts:
            logger.warning("No Reddit data returned from Apify.")
            return []

        # 2. Flatten to a text batch for the LLM
        text_batch = self._prepare_text_batch(raw_posts)

        # 3. Extract pain points via LLM
        pain_points = self._extract_pain_points(text_batch, past_pain_points or [])
        logger.info("Extracted %d pain points.", len(pain_points))
        return pain_points

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _prepare_text_batch(self, raw_posts: List[Dict[str, Any]]) -> str:
        """
        Convert raw Apify Reddit items into a compact text block for the LLM.
        Truncate to avoid context-length issues.
        """
        lines = []
        for post in raw_posts[:40]:  # cap at 40 posts
            title = post.get("title", post.get("search", ""))
            body = post.get("selftext", post.get("body", ""))[:400]
            sub = post.get("subreddit", "unknown")
            url = post.get("url", post.get("postUrl", ""))
            if title or body:
                lines.append(
                    f"--- POST ---\n"
                    f"Subreddit: r/{sub}\n"
                    f"Title: {title}\n"
                    f"Body: {body}\n"
                    f"URL: {url}\n"
                )
        return "\n".join(lines)

    def _extract_pain_points(
        self,
        text_batch: str,
        past_pain_points: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Ask the LLM to pull structured pain points from the Reddit text batch.
        """
        past_titles = [p.get("title", "") for p in past_pain_points]
        context = ""
        if past_titles:
            context = (
                "\n\nAlready-known pain points (avoid exact duplicates):\n"
                + "\n".join(f"- {t}" for t in past_titles[:20])
            )

        user_prompt = (
            f"Here are Reddit posts and comments about trading and prediction markets:\n\n"
            f"{text_batch}"
            f"{context}\n\n"
            "Extract all genuine user pain points from the above data and return them as "
            "a JSON array as described."
        )

        raw = self.llm.complete(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=3000,
        )

        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> List[Dict[str, Any]]:
        clean = re.sub(r"```(?:json)?", "", raw).strip()
        start = clean.find("[")
        end = clean.rfind("]")
        if start == -1 or end == -1:
            logger.error("No JSON array in pain-point extraction response.")
            return []
        try:
            items = json.loads(clean[start : end + 1])
            return [i for i in items if isinstance(i, dict) and "title" in i]
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error in pain extraction: %s", exc)
            return []
