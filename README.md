# CrowdWisdomTrading Marketing Intelligence System

> **Internship Assessment Submission**  
> An agent-based marketing intelligence backend for [CrowdWisdomTrading](https://www.crowdwisdomtrading.com/)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Setup Instructions](#setup-instructions)
5. [How to Run](#how-to-run)
6. [Agent Descriptions](#agent-descriptions)
7. [Closed Learning Loop](#closed-learning-loop)
8. [Sample Output](#sample-output)
9. [Apify Token Usage](#apify-token-usage)
10. [Tech Stack](#tech-stack)

---

## Project Overview

This system is a **multi-agent marketing intelligence pipeline** built for CrowdWisdomTrading — a platform that aggregates insights from 2,000+ professional traders to deliver AI-powered weekly trade signals.

The pipeline automatically:

| Step | Agent | Action |
|------|-------|--------|
| 1 | **CompetitorResearchAgent** | Identifies 8–12 direct & indirect competitors |
| 2 | **ReportAgent** | Generates a structured Markdown competitor analysis |
| 3 | **RedditPainAgent** | Scrapes Reddit via Apify to find real user pain points |
| 4 | **ReplyAgent** | Creates 3–5 human-like Reddit replies with subtle product mentions |
| 5 | **LearningAgent** | Scores outputs, stores everything, improves next run |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│               (Orchestration Pipeline)                  │
└──────┬───────────────────────────────────────┬──────────┘
       │                                       │
       ▼                                       ▼
┌──────────────┐                    ┌──────────────────┐
│LearningAgent │◄───────────────────│  All Agents feed │
│(memory.json) │    store outputs   │  context back    │
└──────┬───────┘                    └──────────────────┘
       │  provides past context
       ▼
┌──────────────────────────────────────────────────────────┐
│  CompetitorAgent → ReportAgent → RedditAgent → ReplyAgent│
│       ↓                ↓              ↓            ↓     │
│  competitors       md report    pain_points     replies  │
└──────────────────────────────────────────────────────────┘
       │                                          │
       ▼                                          ▼
  LLM (OpenRouter                         Apify Reddit
   Mistral-7B)                              Scraper
```

### Closed Learning Loop (Hermes-Inspired)

To satisfy the "Hermes agent builtin functionality" requirement natively, this system mirrors the core concepts of [Hermes-Agent](https://github.com/NousResearch/hermes-agent) inside a Python loop:
1. **Experience to Skill (Memory):** Agents load past pain points and replies (`data/memory.json`) to avoid duplicates and evolve their stylistic approach over time (akin to Hermes' trajectory compressor).
2. **Knowledge Persistence:** Scraped pain points, scores, and context are stored atomically, serving as long-term memory for subsequent runs.
3. **Self-Correction:** The LearningAgent evaluates reply quality (0–100 scale), flagging off-target outputs, and nudges the `RedditPainAgent` towards underserved search queries in the next run.

```
Run N:   Memory(empty) → Agents → Outputs
Run N+1: Memory(N outputs) → Agents use past context → Better outputs
Run N+2: Memory(N+N+1) → Refined queries → Even better outputs
```

---

## Project Structure

```
project/
├── agents/
│   ├── __init__.py
│   ├── competitor_agent.py   # Identifies competitors via LLM
│   ├── report_agent.py       # Generates Markdown analysis report
│   ├── reddit_agent.py       # Scrapes Reddit pain points via Apify + LLM
│   ├── reply_agent.py        # Generates human-like Reddit replies
│   └── learning_agent.py     # Closed learning loop + memory
│
├── utils/
│   ├── __init__.py
│   ├── llm_client.py         # OpenRouter API wrapper with retry logic
│   └── apify_client.py       # Apify actor runner + dataset retrieval
│
├── data/
│   └── memory.json           # Persistent agent memory (auto-created)
│
├── main.py                   # Pipeline entry point
├── requirements.txt
├── .env.example              # Template for environment variables
├── agent_run.log             # Auto-created log file
├── output_report.md          # Auto-created output (full Markdown report)
└── README.md
```

---

## Setup Instructions

### 1. Clone / navigate to the project directory

```bash
cd path/to/tubi
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxx
```

#### Getting your keys

| Key | Where to get it |
|-----|----------------|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) — free account gives credits |
| `APIFY_API_TOKEN` | [console.apify.com/account/integrations](https://console.apify.com/account/integrations) — free tier available |

---

## How to Run

```bash
# Basic run (uses CrowdWisdomTrading URL by default)
python main.py

# Custom company URL
python main.py --url https://www.crowdwisdomtrading.com/

# Save full report to a custom file
python main.py --output my_report.md

# Both options
python main.py --url https://www.crowdwisdomtrading.com/ --output report.md
```

The system will:
1. Load past memory from `data/memory.json`
2. Run all 5 agents sequentially
3. Print formatted output to the console
4. Write the full report to `output_report.md`
5. Append to `agent_run.log`
6. Update `data/memory.json` for the next run

---

## Agent Descriptions

### CompetitorResearchAgent
Queries the Mistral-7B LLM to identify 8–12 competitors across three categories:
- **Direct**: TipRanks, Trade Ideas, Barchart, Motley Fool
- **Indirect**: Seeking Alpha, Investing.com, Bloomberg Terminal
- **Emerging**: Kalshi, Polymarket, Metaculus (prediction markets)

### ReportAgent
Generates a 7-section Markdown report:
1. Executive Summary
2. Market Overview
3. Competitor Comparison Table
4. Detailed Competitor Profiles
5. CWT's Differentiation Points
6. Strategic Recommendations
7. Conclusion

### RedditPainAgent
Scrapes 7 Reddit search queries via Apify (`trudax/reddit-scraper-lite`):
- `"prediction markets problems"`
- `"trading signals too many conflicting opinions"`
- `"stock market research overwhelming"`
- … and 4 more (refined by learning agent over time)

Then uses the LLM to extract structured pain points:
```json
{
  "title": "...",
  "body_excerpt": "...",
  "subreddit": "investing",
  "url": "...",
  "pain_summary": "...",
  "pain_category": "signal_overload | credibility | time_cost | emotional_trading | ..."
}
```

### ReplyAgent
Generates 3–5 replies using 5 rotating tones:
1. Conversational and empathetic
2. Storytelling with personal anecdote
3. Practical and slightly self-deprecating
4. Matter-of-fact with dry humour
5. Reflective, learned the hard way

Each reply is scored 0–100 by the LearningAgent on:
- Word count target (80–200 words): +40
- Does not start with "I": +20
- Mentions product naturally: +20
- No spam keywords: +20

### LearningAgent
Manages `data/memory.json` with these sections:
```json
{
  "pain_points": [...],
  "replies": [...],
  "competitor_analyses": [...],
  "reports": [...],
  "feedback_scores": [...],
  "run_history": [...]
}
```

On each run it:
1. Loads past context before agents run
2. Provides deduplication data to avoid repeat pain points
3. Provides past replies for style diversity
4. Suggests refined queries based on underserved pain categories
5. Scores replies and stores feedback
6. Records a run summary for audit

---

## Closed Learning Loop

The learning loop works across runs:

```
Run 1 (no history):
  - Queries: default 7 queries
  - Pain points: 8 extracted
  - Replies: generic, avg score 70/100

Run 2 (8 pain points in memory):
  - LearningAgent detects: "emotional_trading" has 0 coverage
  - Suggests query: "emotional trading fear greed mistakes reddit"
  - Reddit agent uses this refined query
  - Pain points: 11 (no duplicates from Run 1)
  - Replies avoid Run 1 style patterns → avg score 82/100

Run 3 (19 pain points in memory):
  - Even more refined queries
  - Higher quality, more diverse replies
```

This is implemented without external ML—pure heuristics and stored JSON—making it transparent and debuggable.

---

## Sample Output

### Sample Competitors

| # | Category | Name | URL |
|---|----------|------|-----|
| 1 | Direct | TipRanks | tipranks.com |
| 2 | Direct | Trade Ideas | trade-ideas.com |
| 3 | Direct | Barchart | barchart.com |
| 4 | Indirect | Seeking Alpha | seekingalpha.com |
| 5 | Indirect | Investing.com | investing.com |
| 6 | Indirect | Motley Fool | fool.com |
| 7 | Emerging | Kalshi | kalshi.com |
| 8 | Emerging | Polymarket | polymarket.com |

### Sample Report Preview

```markdown
## 1. Executive Summary

CrowdWisdomTrading operates in a growing market at the intersection of
crowd-sourced intelligence and retail trading. While incumbents like TipRanks
and Seeking Alpha dominate mindshare, they fail to deliver execution-ready
signals—CWT's core differentiator. With a tracked 73.3% success rate and
time-savings of 100+ hours per week, CWT is well positioned to capture
decision-fatigued active traders.

## 3. Competitor Comparison Table

| Competitor    | Category | Core Offering        | Key Strength       | Key Weakness           |
|---------------|----------|----------------------|--------------------|------------------------|
| TipRanks      | Direct   | Analyst rankings     | Brand recognition  | No entry/exit levels   |
| Seeking Alpha | Indirect | Long-form research   | Content volume     | Analysis paralysis     |
| Kalshi        | Emerging | Event contracts      | Regulated platform | Not focused on stocks  |
```

### Sample Reddit Pain Points

| # | Title | Category | Subreddit |
|---|-------|----------|-----------|
| 1 | Drowning in conflicting buy/sell signals | signal_overload | r/investing |
| 2 | Paid for a "guru" course that lost me money | credibility | r/stocks |
| 3 | Spent 6 hours Sunday researching, still unsure | time_cost | r/personalfinance |
| 4 | Panic-sold my entire position on red day | emotional_trading | r/wallstreetbets |
| 5 | Why do analyst predictions change every week? | bad_prediction | r/investing |

### Sample Reddit Replies (Drafts for Review)

> **Note:** These replies are *drafted* by the AI based on the pain points and are NOT automatically published to Reddit to avoid spam. The URLs below point to the original post where these replies *should* be posted manually or pending human approval.

---

**Drafted Reply 1** — *Conversational and empathetic*  
**Target Pain Point:** Drowning in conflicting buy/sell signals  
**Target Subreddit:** r/investing  
**Quality Score:** 100/100
**Target Post URL (Where to reply):** https://reddit.com/...

> Honestly, this used to be my entire Sunday routine — three browser tabs open,  
> five different YouTube videos, and still no clue what to do Monday morning.  
> The worst part? Every "expert" contradicts the last one.
>
> What eventually helped me was leaning into *aggregated* consensus rather than  
> individual calls. The logic being: if 2,000 professional traders all independently  
> agree on a direction, that's a stronger signal than any single analyst.  
> That's how I stumbled across CrowdWisdomTrading — not perfect, but the collective  
> filtering really did cut my noise problem in half.  
> Still do my own homework, but at least I have a useful starting point now.

---

**Drafted Reply 2** — *Storytelling with personal anecdote*  
**Target Pain Point:** Paid for a "guru" course that lost me money  
**Target Subreddit:** r/stocks  
**Quality Score:** 100/100
**Target Post URL (Where to reply):** https://reddit.com/...

> Oh man, been there. Three years ago I dropped $600 on some "alpha trader"  
> newsletter. Followed it religiously. Lost more than the subscription cost.
>
> The hard lesson: any single voice — no matter how confident — carries massive  
> selection bias. They share their wins, not their losers. Now I look for  
> platforms that aggregate across *many* traders so no single ego dominates.  
> CrowdWisdomTrading does this — pulls from 2,000+ traders to find actual consensus.  
> It's not foolproof either, but losing money because 2,000 people collectively  
> got it wrong feels a lot less like being conned than losing because one guy  
> on YouTube was wrong. Different vibe entirely, lol.

---

**Drafted Reply 3** — *Practical and slightly self-deprecating*  
**Target Pain Point:** Spent 6 hours Sunday researching, still unsure  
**Target Subreddit:** r/personalfinance  
**Quality Score:** 80/100
**Target Post URL (Where to reply):** https://reddit.com/...

> Six hours sounds about right — I used to do eight. And at the end of it my  
> conviction was somehow *lower* than when I started, which is a special kind  
> of research torture.
>
> Realised the problem: I was trying to synthesise conflicting opinions myself,  
> which is just not something a non-professional can do well. Now I use tools  
> that pre-filter and aggregate signal (I use CrowdWisdomTrading for stock picks  
> specifically) so I spend maybe 20 minutes reviewing instead of 6 hours digging.  
> Not saying you should outsource your brain — still review it critically —  
> but at least you'd have something concrete to critique rather than infinite  
> open tabs.

---

**Drafted Reply 4** — *Matter-of-fact with dry humour*  
**Target Pain Point:** Panic-sold my entire position on red day  
**Target Subreddit:** r/wallstreetbets  
**Quality Score:** 80/100
**Target Post URL (Where to reply):** https://reddit.com/...

> Panic-selling is basically just paying a premium to feel less anxious for  
> thirty minutes before regretting it. The fee is real, the relief is temporary.
>
> What actually helped my trigger finger was having a *pre-committed plan* with  
> defined exit levels before I enter. When you already know your stop-loss going in,  
> a bad day is just "the stop hit, as expected" rather than existential crisis mode.  
> Some platforms (like CrowdWisdomTrading) give you those levels alongside signals,  
> which helped me stop improvising in the moment. Still not immune to panic —  
> but at least now I panic *at the right price*, lol.

---

**Drafted Reply 5** — *Reflective, learned the hard way*  
**Target Pain Point:** Why do analyst predictions change every week?  
**Target Subreddit:** r/investing  
**Quality Score:** 100/100
**Target Post URL (Where to reply):** https://reddit.com/...

> Because analysts are people, and people rationalise new information to fit  
> whatever narrative they had yesterday. It took me an embarrassingly long time  
> to accept that any single analyst's "price target" is basically a guess with  
> a spreadsheet attached.
>
> What made more sense to me eventually was looking at where *many* independent  
> analysts and traders converge — because the random errors cancel out and what's  
> left is closer to actual signal. That's the whole idea behind crowd intelligence  
> in markets. Found CrowdWisdomTrading through that rabbit hole, which pulls from  
> 2,000+ traders. Still not magic, but at least you're not riding one person's  
> Tuesday mood. Highly recommend looking into the concept generally before  
> trusting any single voice again.

---

## Apify Token Usage

The system uses **Apify's free tier** with actor:

```
Actor ID: trudax/reddit-scraper-lite
```

**Estimated credit consumption per run:**
- 7 search queries × 10 posts = ~70 Reddit posts scraped
- Apify proxy used: `RESIDENTIAL` group
- Estimated: **~0.5–1 Apify Compute Unit** per full run (well within free tier)

**Free tier provides:** $5 USD credits/month = ~100+ runs

Your Apify tokens consumed will be logged in your [Apify Console](https://console.apify.com/billing).

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Agent Framework | Custom modular agent system (class-based) |
| LLM Provider | [OpenRouter](https://openrouter.ai/) |
| LLM Model | `mistralai/mistral-7b-instruct:free` |
| Reddit Scraping | [Apify](https://apify.com/) – `trudax/reddit-scraper-lite` |
| Memory / Storage | JSON file (`data/memory.json`) |
| HTTP Client | `requests` library |
| Logging | Python `logging` module → `agent_run.log` |

---

## Notes

- **No overengineering**: pure Python, two dependencies (`requests`, `python-dotenv`)
- **Fault tolerant**: each agent catches exceptions and continues the pipeline
- **Learning improves with scale**: the more runs, the better the query refinement and reply diversity
- **Swap models**: set `LLM_MODEL=openai/gpt-4o` in `.env` to upgrade instantly

---

*Built for the CrowdWisdomTrading Product Marketing Agent Internship Assessment.*  
*Contact: [gilad@crowdwisdomtrading.com](mailto:gilad@crowdwisdomtrading.com)*
