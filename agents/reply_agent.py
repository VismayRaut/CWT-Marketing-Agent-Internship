"""
reply_agent.py
--------------
ReplyAgent

Given a set of Reddit pain points, generates 3–5 human-sounding Reddit
replies that:
  - Sound like a real person who relates to the problem
  - Do NOT look like spam or an ad
  - Subtly mention CrowdWisdomTrading as something that has helped
  - Vary in tone: conversational, empathetic, storytelling

Input  : pain points (list[dict]), past replies (list[dict]) from LearningAgent
Output : list of reply dicts
         { pain_point_title, subreddit, url, reply_text, tone }
"""

import logging
import json
import re
import random
from typing import List, Dict, Any, Optional

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a real retail trader who is active on Reddit.
You have been using various tools to improve your trading results and want to
help others who are frustrated with the same problems you used to face.

When writing Reddit replies:
- Write in first person, casual Reddit tone
- Keep replies between 80-200 words
- Start with empathy or personal experience, NOT with a product name
- Mention CrowdWisdomTrading (https://crowdwisdomtrading.com) only ONCE per reply,
  naturally, as something you personally tried — not as an advertisement
- Never use sales language ("amazing", "best ever", "sign up now", etc.)
- Each reply must feel unique; vary the opening, tone, and story
- Include a Redditor-style conversational element (small aside, slight humour, etc.)
- DO NOT start with "I" — vary the openings

Your goal is to be genuinely helpful while organically mentioning a solution.
"""

TONE_STYLES = [
    "conversational and empathetic",
    "storytelling with a personal anecdote",
    "practical and slightly self-deprecating",
    "matter-of-fact with a touch of dry humour",
    "reflective, like someone who learned the hard way",
]


class ReplyAgent:
    """
    Generates human-like Reddit replies for identified pain points.

    Parameters
    ----------
    llm            : LLMClient
    replies_per_run: int   – how many total replies to generate (3–5)
    """

    def __init__(self, llm: LLMClient, replies_per_run: int = 5):
        self.llm = llm
        self.replies_per_run = max(3, min(replies_per_run, 5))
        logger.info("ReplyAgent initialised (replies_per_run=%d).", self.replies_per_run)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        pain_points: List[Dict[str, Any]],
        past_replies: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate Reddit replies for the most relevant pain points.

        Parameters
        ----------
        pain_points  : list[dict]  – output of RedditPainAgent
        past_replies : list[dict]  – previous replies stored by LearningAgent

        Returns
        -------
        list[dict]  – reply objects
        """
        if not pain_points:
            logger.warning("No pain points provided to ReplyAgent.")
            return []

        # Pick the top N pain points to reply to (prioritise variety in category)
        selected = self._select_pain_points(pain_points, self.replies_per_run)
        logger.info("ReplyAgent generating replies for %d pain points.", len(selected))

        replies = []
        for i, pain in enumerate(selected):
            tone = TONE_STYLES[i % len(TONE_STYLES)]
            try:
                reply_text = self._generate_reply(pain, tone, past_replies or [])
                reply = {
                    "pain_point_title": pain.get("title", ""),
                    "pain_summary": pain.get("pain_summary", ""),
                    "subreddit": pain.get("subreddit", ""),
                    "url": pain.get("url", ""),
                    "reply_text": reply_text,
                    "tone": tone,
                }
                replies.append(reply)
                logger.info("Reply %d generated (tone: %s).", i + 1, tone)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error generating reply %d: %s", i + 1, exc)

        return replies

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _select_pain_points(
        self, pain_points: List[Dict[str, Any]], n: int
    ) -> List[Dict[str, Any]]:
        """
        Pick *n* pain points, preferring category diversity.
        Falls back to random sample if not enough distinct categories.
        """
        seen_categories: set = set()
        selected = []
        # First pass – one per category
        for p in pain_points:
            cat = p.get("pain_category", "other")
            if cat not in seen_categories:
                selected.append(p)
                seen_categories.add(cat)
            if len(selected) >= n:
                break
        # Second pass – fill remaining slots
        remaining = [p for p in pain_points if p not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[: n - len(selected)])
        return selected[:n]

    def _generate_reply(
        self,
        pain: Dict[str, Any],
        tone: str,
        past_replies: List[Dict[str, Any]],
    ) -> str:
        """
        Ask the LLM to craft a single reply for one pain point.
        """
        past_texts = "\n---\n".join(
            r.get("reply_text", "") for r in past_replies[-10:]
        )
        avoid_block = (
            f"\n\nAvoid repeating these previously written reply styles:\n{past_texts}"
            if past_texts
            else ""
        )

        user_prompt = (
            f"Pain Point Title: {pain.get('title', '')}\n"
            f"Pain Summary: {pain.get('pain_summary', '')}\n"
            f"Subreddit: r/{pain.get('subreddit', 'investing')}\n"
            f"Original Post URL: {pain.get('url', '')}\n\n"
            f"Write a Reddit reply in this tone: {tone}.\n"
            f"The reply is for a post where the user is expressing this frustration."
            f"{avoid_block}\n\n"
            "Return ONLY the reply text itself. No preamble, no labels."
        )

        return self.llm.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.85,
            max_tokens=400,
        )
