"""
learning_agent.py
-----------------
LearningAgent – Closed Learning Loop

Responsibilities:
1. Persist all agent outputs (pain points, replies, competitor analyses, reports)
   to data/memory.json
2. Retrieve stored data to give other agents context (deduplication, style evolution)
3. Maintain a simple feedback mechanism so future runs improve over time:
   - Track which pain-point categories appeared most
   - Suggest refined search queries based on history
   - Flag reply tones that hit the 80-200 word target

This is the "closed loop": each run reads past context → agents use it →
outputs are stored → next run reads updated context.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "memory.json"
)

EMPTY_MEMORY: Dict[str, Any] = {
    "pain_points": [],
    "replies": [],
    "competitor_analyses": [],
    "reports": [],
    "feedback_scores": [],
    "run_history": [],
}


class LearningAgent:
    """
    Manages persistent memory and drives the closed learning loop.

    Parameters
    ----------
    memory_path : str
        Path to the JSON memory file.
    """

    def __init__(self, memory_path: str = DEFAULT_MEMORY_PATH):
        self.memory_path = os.path.abspath(memory_path)
        self._memory: Dict[str, Any] = self._load()
        logger.info("LearningAgent initialised. Memory file: %s", self.memory_path)

    # ==================================================================
    # ── Persistence
    # ==================================================================

    def _load(self) -> Dict[str, Any]:
        """Load memory from disk, creating the file if it doesn't exist."""
        if not os.path.exists(self.memory_path):
            logger.info("No memory file found — creating fresh memory store.")
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            self._write(EMPTY_MEMORY)
            return dict(EMPTY_MEMORY)
        try:
            with open(self.memory_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.info(
                "Memory loaded: %d pain points, %d replies, %d runs.",
                len(data.get("pain_points", [])),
                len(data.get("replies", [])),
                len(data.get("run_history", [])),
            )
            return data
        except (json.JSONDecodeError, IOError) as exc:
            logger.error("Could not load memory: %s. Starting fresh.", exc)
            return dict(EMPTY_MEMORY)

    def _write(self, data: Dict[str, Any]) -> None:
        """Write memory to disk atomically (write-then-rename)."""
        tmp_path = self.memory_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.memory_path)
        except IOError as exc:
            logger.error("Failed to write memory: %s", exc)

    def save(self) -> None:
        """Persist in-memory state to disk."""
        self._write(self._memory)
        logger.info("Memory saved to %s.", self.memory_path)

    # ==================================================================
    # ── Store outputs
    # ==================================================================

    def store_pain_points(self, pain_points: List[Dict[str, Any]]) -> None:
        """Append new pain points (deduplicating by title)."""
        existing_titles = {p.get("title", "") for p in self._memory["pain_points"]}
        new_count = 0
        for pp in pain_points:
            if pp.get("title", "") not in existing_titles:
                pp["stored_at"] = _now()
                self._memory["pain_points"].append(pp)
                existing_titles.add(pp.get("title", ""))
                new_count += 1
        logger.info("Stored %d new pain points (skipped %d duplicates).",
                    new_count, len(pain_points) - new_count)

    def store_replies(self, replies: List[Dict[str, Any]]) -> None:
        """Append new reply objects."""
        for r in replies:
            r["stored_at"] = _now()
            self._memory["replies"].append(r)
        logger.info("Stored %d new replies.", len(replies))

    def store_competitors(self, competitors: List[Dict[str, Any]], company_url: str) -> None:
        """Store a competitor snapshot keyed by company URL + timestamp."""
        entry = {
            "company_url": company_url,
            "competitors": competitors,
            "stored_at": _now(),
        }
        self._memory["competitor_analyses"].append(entry)
        logger.info("Stored competitor analysis for %s.", company_url)

    def store_report(self, report: str, company_url: str) -> None:
        """Store a generated report (truncated for memory efficiency)."""
        entry = {
            "company_url": company_url,
            "report_preview": report[:1000],
            "full_report_length": len(report),
            "stored_at": _now(),
        }
        self._memory["reports"].append(entry)
        logger.info("Stored report (%d chars).", len(report))

    def record_run(self, summary: Dict[str, Any]) -> None:
        """Record a run-level summary with timestamp."""
        summary["run_at"] = _now()
        self._memory["run_history"].append(summary)
        logger.info("Run recorded in history.")

    # ==================================================================
    # ── Retrieve context for agents
    # ==================================================================

    def get_past_pain_points(
        self, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Return the most recent *limit* pain points."""
        return self._memory["pain_points"][-limit:]

    def get_past_replies(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent *limit* replies."""
        return self._memory["replies"][-limit:]

    def get_last_competitors(
        self, company_url: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Return the most recent competitor list for *company_url*, if any."""
        matches = [
            e for e in self._memory["competitor_analyses"]
            if e.get("company_url") == company_url
        ]
        return matches[-1]["competitors"] if matches else None

    # ==================================================================
    # ── Learning / Improvement
    # ==================================================================

    def suggest_refined_queries(self) -> List[str]:
        """
        Analyse stored pain points and suggest new Reddit search queries
        targeting the most represented pain categories that still need
        more coverage.

        Returns a list of up to 5 refined queries.
        """
        pain_points = self._memory["pain_points"]
        if len(pain_points) < 5:
            logger.info("Not enough data to refine queries yet.")
            return []

        # Count categories
        from collections import Counter
        category_counts = Counter(
            p.get("pain_category", "other") for p in pain_points
        )
        # Find underserved categories
        all_categories = [
            "signal_overload", "credibility", "time_cost",
            "emotional_trading", "bad_prediction", "research_difficulty",
        ]
        underserved = [c for c in all_categories if category_counts.get(c, 0) < 3]

        category_to_query = {
            "signal_overload": "too many trading signals conflicting advice",
            "credibility": "how to verify trading guru credibility reddit",
            "time_cost": "spending too much time on stock research reddit",
            "emotional_trading": "emotional trading fear greed mistakes",
            "bad_prediction": "wrong stock prediction analyst wrong reddit",
            "research_difficulty": "how to research stocks beginners overwhelmed",
        }

        refined = [category_to_query[c] for c in underserved if c in category_to_query]
        logger.info("Suggested %d refined queries based on memory.", len(refined))
        return refined[:5]

    def evaluate_reply_quality(self, reply: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a reply on simple heuristics and attach feedback metadata.

        Scoring (0–100):
        - word count in 80-200 range  : +40
        - does NOT start with "I"     : +20
        - mentions product URL/name   : +20
        - no sales keywords present   : +20

        Returns the reply dict enriched with a 'quality_score' key.
        """
        text = reply.get("reply_text", "")
        words = text.split()
        score = 0

        if 80 <= len(words) <= 200:
            score += 40

        if not text.startswith("I "):
            score += 20

        product_mentions = any(
            kw in text.lower()
            for kw in ["crowdwisdom", "crowdwisdomtrading", "crowdwisdom trading"]
        )
        if product_mentions:
            score += 20

        spam_keywords = [
            "sign up now", "click here", "best ever", "amazing product",
            "limited offer", "buy now",
        ]
        if not any(kw in text.lower() for kw in spam_keywords):
            score += 20

        reply["quality_score"] = score
        self._memory["feedback_scores"].append(
            {"score": score, "tone": reply.get("tone", ""), "scored_at": _now()}
        )
        return reply

    def get_avg_quality_score(self) -> float:
        """Return the average reply quality score across all runs."""
        scores = self._memory.get("feedback_scores", [])
        if not scores:
            return 0.0
        return sum(s["score"] for s in scores) / len(scores)

    def get_memory_stats(self) -> Dict[str, Any]:
        """Return a summary dict of current memory contents."""
        return {
            "total_pain_points": len(self._memory["pain_points"]),
            "total_replies": len(self._memory["replies"]),
            "total_runs": len(self._memory["run_history"]),
            "avg_reply_quality": round(self.get_avg_quality_score(), 1),
            "competitor_snapshots": len(self._memory["competitor_analyses"]),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
