"""
main.py
-------
CrowdWisdomTrading Marketing Intelligence System
Entry point – orchestrates all agents sequentially.

Usage
-----
    python main.py
    python main.py --url https://www.crowdwisdomtrading.com/ --output report.md

Environment Variables Required
-------------------------------
    OPENROUTER_API_KEY   : Your OpenRouter API key
    APIFY_API_TOKEN      : Your Apify API token

Optional
--------
    LLM_MODEL            : Override default LLM model (default: mistral-7b free tier)
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Load .env file automatically if present (users don't need to set system env vars)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed – rely on system env vars

# ---------------------------------------------------------------------------
# Logging setup (must happen before agent imports)
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent_run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from utils.llm_client import LLMClient
from utils.apify_client import ApifyClient
from agents.competitor_agent import CompetitorResearchAgent
from agents.report_agent import ReportAgent
from agents.reddit_agent import RedditPainAgent
from agents.reply_agent import ReplyAgent
from agents.learning_agent import LearningAgent


# ===========================================================================
# Helpers
# ===========================================================================

def _banner(text: str) -> None:
    width = 70
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def _check_env() -> None:
    """Fail fast if required API keys are missing."""
    missing = []
    if not os.getenv("OPENROUTER_API_KEY"):
        missing.append("OPENROUTER_API_KEY")
    if not os.getenv("APIFY_API_TOKEN"):
        missing.append("APIFY_API_TOKEN")
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        print(
            "\n❌  ERROR: The following environment variables are not set:\n"
            + "\n".join(f"   • {v}" for v in missing)
            + "\n\nSee README.md for setup instructions."
        )
        sys.exit(1)


# ===========================================================================
# Main pipeline
# ===========================================================================

def run_pipeline(company_url: str, output_file: str | None = None) -> None:
    start_time = datetime.utcnow()
    _banner("CrowdWisdomTrading Marketing Intelligence System")
    print(f"  Company URL : {company_url}")
    print(f"  Started at  : {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # ── 1. Clients -----------------------------------------------------------
    logger.info("Initialising clients…")
    llm = LLMClient(model=os.getenv("LLM_MODEL", "mistralai/mistral-7b-instruct:free"))
    apify = ApifyClient()

    # ── 2. Learning Agent (load memory FIRST) --------------------------------
    _section("Loading Memory (LearningAgent)")
    learning = LearningAgent()
    stats = learning.get_memory_stats()
    print(f"  📂 Memory stats: {stats}")

    past_pain_points = learning.get_past_pain_points()
    past_replies = learning.get_past_replies()
    refined_queries = learning.suggest_refined_queries()
    if refined_queries:
        print(f"  🔍 Refined search queries from memory:\n    " +
              "\n    ".join(refined_queries))

    # ── 3. CompetitorResearchAgent -------------------------------------------
    _section("Step 1 · Identifying Competitors")
    competitor_agent = CompetitorResearchAgent(llm)
    competitors = competitor_agent.run(company_url)

    if not competitors:
        logger.warning("No competitors returned – using cached data if available.")
        competitors = learning.get_last_competitors(company_url) or []

    print(f"\n  ✅  Found {len(competitors)} competitors:\n")
    for i, c in enumerate(competitors, 1):
        print(f"  {i:2d}. [{c['category'].upper()}] {c['name']}")
        print(f"       {c['url']}")
        print(f"       {c['description'][:100]}…" if len(c['description']) > 100
              else f"       {c['description']}")

    # Store
    learning.store_competitors(competitors, company_url)

    # ── 4. ReportAgent -------------------------------------------------------
    _section("Step 2 · Generating Competitor Analysis Report")
    report_agent = ReportAgent(llm)
    report = report_agent.run(competitors, company_url)
    print(f"\n  ✅  Report generated ({len(report)} chars).\n")
    # Print first 800 chars as preview
    print(report[:800] + "\n  … [truncated – see output file for full report]\n"
          if len(report) > 800 else report)

    # Store
    learning.store_report(report, company_url)

    # ── 5. RedditPainAgent ---------------------------------------------------
    _section("Step 3 · Scraping Reddit for Pain Points")
    reddit_agent = RedditPainAgent(llm, apify)
    # Use refined queries if the learning agent suggested any, supplemented
    # by a subset of the default queries
    from agents.reddit_agent import REDDIT_QUERIES
    queries_to_use = (refined_queries + REDDIT_QUERIES)[:7] if refined_queries else REDDIT_QUERIES
    pain_points = reddit_agent.run(
        queries=queries_to_use, past_pain_points=past_pain_points
    )

    print(f"\n  ✅  Extracted {len(pain_points)} pain points:\n")
    for i, pp in enumerate(pain_points, 1):
        cat = pp.get("pain_category", "other")
        print(f"  {i:2d}. [{cat}] {pp.get('title', '')}")
        print(f"       {pp.get('pain_summary', '')[:100]}")

    # Store
    learning.store_pain_points(pain_points)

    # ── 6. ReplyAgent --------------------------------------------------------
    _section("Step 4 · Generating Reddit Replies")
    reply_agent = ReplyAgent(llm, replies_per_run=5)
    replies = reply_agent.run(pain_points, past_replies=past_replies)

    print(f"\n  ✅  Generated {len(replies)} human-like Reddit replies:\n")
    for i, r in enumerate(replies, 1):
        print(f"  ── Reply {i} (tone: {r['tone']}) ──────────────────────")
        print(f"  🎯 Pain: {r['pain_point_title']}")
        print(f"  📍 Subreddit: r/{r.get('subreddit','?')}   |   {r.get('url','')}")
        print()
        # Indent reply text for readability
        for line in r["reply_text"].splitlines():
            print(f"  {line}")
        print()

    # ── 7. LearningAgent – score & store replies ----------------------------
    _section("Step 5 · Closing the Learning Loop")
    scored_replies = [learning.evaluate_reply_quality(r) for r in replies]
    learning.store_replies(scored_replies)

    avg_score = learning.get_avg_quality_score()
    print(f"\n  📊 Average reply quality score: {avg_score:.1f} / 100")
    for r in scored_replies:
        print(f"     • {r['pain_point_title'][:50]:<50}  score={r['quality_score']}")

    # Save memory
    learning.save()

    # ── 8. Run history record ------------------------------------------------
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    learning.record_run({
        "company_url": company_url,
        "competitors_found": len(competitors),
        "pain_points_found": len(pain_points),
        "replies_generated": len(replies),
        "avg_reply_quality": round(avg_score, 1),
        "elapsed_seconds": round(elapsed, 1),
    })
    learning.save()

    # ── 9. Write output file ------------------------------------------------
    if output_file:
        _write_output(
            output_file, company_url, competitors, report, pain_points, scored_replies
        )
        print(f"\n  📄 Full output written to: {output_file}")

    # ── 10. Summary ----------------------------------------------------------
    _banner("Pipeline Complete")
    print(f"  ⏱  Elapsed : {elapsed:.1f}s")
    print(f"  🏢 Competitors   : {len(competitors)}")
    print(f"  😤 Pain Points   : {len(pain_points)}")
    print(f"  💬 Replies       : {len(replies)}")
    print(f"  📈 Avg Quality   : {avg_score:.1f}/100")
    print(f"  📂 Memory Stats  : {learning.get_memory_stats()}")
    print()


def _write_output(
    path: str,
    company_url: str,
    competitors: list,
    report: str,
    pain_points: list,
    replies: list,
) -> None:
    """Write a full Markdown output file."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# CrowdWisdomTrading Marketing Intelligence Report",
        f"*Generated: {ts}*\n",
        f"**Company:** {company_url}\n",
        "---\n",
        "## Competitors\n",
    ]
    for i, c in enumerate(competitors, 1):
        lines.append(
            f"**{i}. {c['name']}** ({c['category']})  \n"
            f"{c['url']}  \n"
            f"{c['description']}\n"
        )
    lines += ["\n---\n", "## Competitor Analysis Report\n", report, "\n---\n",
              "## Reddit Pain Points\n"]
    for i, pp in enumerate(pain_points, 1):
        lines.append(
            f"**{i}. {pp.get('title','')}**  \n"
            f"Category: `{pp.get('pain_category','')}`  \n"
            f"{pp.get('pain_summary','')}  \n"
            f"Source: {pp.get('url','')}\n"
        )
    lines += ["\n---\n", "## Reddit Replies (Drafts for Review)\n", "> **Note:** These replies are *drafted* by the AI based on the pain points and are NOT automatically published to Reddit to avoid spam. The URLs below point to the original post where these replies *should* be posted manually or pending human approval.\n\n"]
    for i, r in enumerate(replies, 1):
        lines.append(
            f"### Drafted Reply {i} — {r['tone']}\n"
            f"**Target Pain Point:** {r['pain_point_title']}  \n"
            f"**Target Subreddit:** r/{r.get('subreddit','?')}  \n"
            f"**Quality Score:** {r.get('quality_score', 'N/A')}/100  \n"
            f"**Target Post URL (Where to reply):** {r.get('url','')}\n\n"
            f"{r['reply_text']}\n"
        )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ===========================================================================
# CLI
# ===========================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CrowdWisdomTrading Marketing Intelligence Agent System"
    )
    parser.add_argument(
        "--url",
        default="https://www.crowdwisdomtrading.com/",
        help="Company URL to analyse (default: CrowdWisdomTrading)",
    )
    parser.add_argument(
        "--output",
        default="output_report.md",
        help="Path for the Markdown output report (default: output_report.md)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _check_env()
    run_pipeline(company_url=args.url, output_file=args.output)
