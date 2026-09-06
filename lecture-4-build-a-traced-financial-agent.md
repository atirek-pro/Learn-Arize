# Lecture 4: Build a Traced Financial Agent

> **Learning objective:** Build a working two-turn financial research agent with Google ADK, understand why its behavior is non-deterministic by design, and see its execution as a trace inside Arize AX.

This lecture builds directly on the tracing setup from Lecture 3 — if you haven't already installed `arize-otel`, `openinference-instrumentation-google-adk`, and `google-adk`, and set up your Arize AX credentials, do that first.

---

## 1. What We're Building

A financial analysis chatbot that works in **two conversational turns**:

1. **Research** — the agent uses a web search tool to pull current financial data on requested ticker symbols.
2. **Write** — the agent turns that research into a concise, readable report.

Because tracing is instrumented the same way as in Lecture 3, every step of both turns — the search calls, the reasoning, the final write-up — is automatically captured and sent to Arize AX, with no manual logging.

---

## 2. Set Up the Project

### Step 1: Create the ADK project

```bash
adk create financial_report_agent
```

This scaffolds the project the same way it did in Lecture 3, generating an `agent.py` file with a `root_agent` placeholder.

### Step 2: Set your environment variables

If this is a new project folder, add a `.env` file with the same two values from Lecture 3:

```bash
ARIZE_AX_SPACE_ID=your-space-id-here
ARIZE_AX_API_KEY=your-api-key-here
```

### Step 3: Replace `agent.py`

Replace the generated `agent.py` with the full agent code below.

---

## 3. The Agent Code

```python
"""
Financial Analysis Agent

Experiment:
    Google ADK + OpenInference + explicit Python tool

Unlike the previous version, this agent does NOT use Google's
built-in google_search tool.

Instead, the LLM explicitly calls a normal Python function:
    yahoo_finance_research()

This allows us to determine whether normal ADK tool execution
produces clean TOOL spans in Arize/OpenInference.
"""

import os
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv

from arize.otel import register
from google.adk.agents import Agent
from openinference.instrumentation.google_adk import GoogleADKInstrumentor


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# ARIZE / OPENINFERENCE
# ============================================================

trace_provider = register(
    space_id=os.getenv("ARIZE_AX_SPACE_ID"),
    api_key=os.getenv("ARIZE_AX_API_KEY"),
    project_name="FinancialAnalysisAgent",
)

GoogleADKInstrumentor().instrument(
    tracer_provider=trace_provider
)


# ============================================================
# YAHOO FINANCE TOOL
# ============================================================

def yahoo_finance_research(
    tickers: str,
    focus: str,
) -> dict:
    """
    Fetch financial data and recent news from Yahoo Finance.

    Args:
        tickers:
            Comma-separated ticker symbols.
            Example: "AAPL" or "AAPL,MSFT"

        focus:
            Specific financial analysis focus.
            Example:
            "revenue growth and services segment"

    Returns:
        Structured financial research data.
    """

    ticker_list = [
        ticker.strip().upper()
        for ticker in tickers.split(",")
        if ticker.strip()
    ]

    if not ticker_list:
        return {
            "status": "error",
            "message": "No valid ticker symbols provided.",
        }

    results = []

    for symbol in ticker_list:

        try:

            ticker = yf.Ticker(symbol)

            # ------------------------------------------------
            # Basic company information
            # ------------------------------------------------

            info = ticker.info

            company_name = info.get(
                "longName",
                info.get("shortName", symbol),
            )

            # ------------------------------------------------
            # Current / recent market data
            # ------------------------------------------------

            history = ticker.history(
                period="5d"
            )

            recent_prices = []

            if not history.empty:

                for index, row in history.iterrows():

                    recent_prices.append({
                        "date": index.strftime("%Y-%m-%d"),
                        "open": (
                            float(row["Open"])
                            if row["Open"] is not None
                            else None
                        ),
                        "high": (
                            float(row["High"])
                            if row["High"] is not None
                            else None
                        ),
                        "low": (
                            float(row["Low"])
                            if row["Low"] is not None
                            else None
                        ),
                        "close": (
                            float(row["Close"])
                            if row["Close"] is not None
                            else None
                        ),
                        "volume": (
                            int(row["Volume"])
                            if row["Volume"] is not None
                            else None
                        ),
                    })

            # ------------------------------------------------
            # Recent Yahoo Finance news
            # ------------------------------------------------

            news_items = []

            try:

                news = ticker.news

                for item in news[:10]:

                    content = item.get(
                        "content",
                        {}
                    )

                    title = content.get(
                        "title"
                    )

                    publisher = content.get(
                        "provider", {}
                    ).get(
                        "displayName"
                    )

                    canonical_url = (
                        content
                        .get("canonicalUrl", {})
                        .get("url")
                    )

                    news_items.append({
                        "title": title,
                        "publisher": publisher,
                        "url": canonical_url,
                    })

            except Exception as news_error:

                news_items.append({
                    "error": str(news_error)
                })

            # ------------------------------------------------
            # Financial metrics relevant to analysis
            # ------------------------------------------------

            financial_metrics = {
                "market_cap": info.get("marketCap"),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "profit_margins": info.get("profitMargins"),
                "operating_margins": info.get("operatingMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "return_on_equity": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "dividend_yield": info.get("dividendYield"),
            }

            results.append({
                "ticker": symbol,
                "company_name": company_name,
                "focus": focus,
                "financial_metrics": financial_metrics,
                "recent_prices": recent_prices,
                "recent_news": news_items,
            })

        except Exception as e:

            results.append({
                "ticker": symbol,
                "focus": focus,
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "success",
        "retrieved_at": datetime.utcnow().isoformat(),
        "requested_tickers": ticker_list,
        "focus": focus,
        "results": results,
    }


# ============================================================
# AGENT
# ============================================================

root_agent = Agent(
    name="financial_report_agent",

    model="gemini-flash-latest",

    description=(
        "A financial analysis agent that retrieves financial data "
        "and recent financial news using an explicit Yahoo Finance "
        "Python tool, then produces a concise financial report."
    ),

    instruction=(
        "You are a financial analysis agent.\n\n"

        "Your job is to produce a concise financial analysis report "
        "based on current data retrieved from Yahoo Finance.\n\n"

        "Follow this workflow:\n\n"

        "1. UNDERSTAND THE REQUEST\n"
        "   - Identify the requested ticker symbols.\n"
        "   - Identify the user's requested analytical focus.\n\n"

        "2. RESEARCH\n"
        "   - You MUST call the yahoo_finance_research tool.\n"
        "   - Pass the requested ticker symbols to the tool.\n"
        "   - Pass the user's requested focus to the tool.\n"
        "   - Do not invent financial data.\n\n"

        "3. ANALYZE\n"
        "   - Review the financial metrics returned by the tool.\n"
        "   - Review recent price information.\n"
        "   - Review the recent news returned by the tool.\n"
        "   - Relate the available evidence to the requested focus.\n\n"

        "4. WRITE\n"
        "   - Produce a concise financial report.\n"
        "   - Clearly distinguish factual information from analysis "
        "or interpretation.\n"
        "   - Mention important data limitations when applicable.\n"
        "   - Do not fabricate missing information.\n"
    ),

    tools=[
        yahoo_finance_research
    ],
)
```

**No extra install needed for search:** `google_search` is imported from `google.adk.tools`, meaning it ships as part of the `google-adk` package you already installed in Lecture 3 — there's no separate search API package to configure here.

---

## 4. How the Pieces Fit Together

The top of the file — `load_dotenv()`, `register(...)`, `GoogleADKInstrumentor().instrument(...)` — is exactly the tracing setup from Lecture 3. It's identical because instrumentation is a one-time, per-project setup, not something you rewrite for every new agent.

What's new here:

- **`google_search`** is passed into `tools=[google_search]`, giving the agent access to real web data instead of relying only on what the model already knows.
- **`instruction`** encodes the _entire_ two-step workflow (RESEARCH, then WRITE) as standing behavioral guidance for the agent — it applies throughout the conversation, not just once.
- **`RESEARCH_PROMPT`** and **`WRITE_PROMPT`** are templates for what _you_, the user, send the agent — one per turn. They're not passed into the `Agent(...)` definition directly; they're the two messages that drive the two-turn conversation described next.

---

## 5. The Two-Turn Pattern

The agent's `instruction` defines _how_ it should behave; `RESEARCH_PROMPT` and `WRITE_PROMPT` are the two actual messages you send it, one per turn:

```python
RESEARCH_PROMPT.format(tickers="AAPL, MSFT", focus="Q3 earnings and outlook")
# → "Research AAPL, MSFT. Focus on: Q3 earnings and outlook.
#    Use web search to find current financial data, news, and trends."

WRITE_PROMPT
# → "Now write a concise financial report based on your research above."
```

**Turn 1** sends the filled-in `RESEARCH_PROMPT`. The agent uses `google_search` to gather current data and reasons over it.

**Turn 2** sends `WRITE_PROMPT` — a much shorter message. Notice it doesn't repeat any of the research. It doesn't need to: ADK keeps conversation context across turns, so the agent still has access to everything it found in Turn 1 when it writes the report in Turn 2.

This is _why_ it's a two-turn pattern rather than one long instruction: it splits "gather information" from "produce the final output" into separate steps you can inspect independently — which matters a lot once you look at the trace (Section 7).

---

## 6. This Is Non-Deterministic by Design

Run the same two prompts twice, and you likely won't get an identical report both times — the wording will differ, and even _what_ gets emphasized in the report might shift slightly, since the model is generating language, not filling in a fixed template.

This is expected, not a bug. What should stay consistent between runs is captured in the instruction's guardrails: sourcing claims from real search results, not inventing figures, and separating fact from analysis. Those constraints are exactly the kind of thing you'd check with an **eval** (Lecture 2) rather than expecting word-for-word repeatability — you're not testing for one exact output, you're testing whether the output stays within the boundaries the instruction sets.

---

## 7. Open the Trace in Arize AX

After running the agent through both turns, open your project in Arize AX. You'll see a trace with spans for each step: the model interpreting the research prompt, the `google_search` tool call(s), the reasoning over the results, and finally the write-up in Turn 2.

This is **observability** in practice, not just in theory: instead of only seeing the final report, you can inspect _which_ search results the agent actually used, whether its reasoning in Turn 1 is what fed into Turn 2 correctly, and where — if the final report is wrong or thin — the process broke down. This is the direct, hands-on version of the span-level visibility discussed in Lecture 2.

---

## Key Takeaways

1. **Tracing setup doesn't change per agent** — the `register()` / `Instrumentor().instrument()` pattern from Lecture 3 is reused as-is here.
2. **Tools extend what an agent can do** — `google_search` gives this agent access to current data it couldn't otherwise have.
3. **`instruction` sets standing behavior; turn-specific prompts drive the conversation** — the workflow lives in the instruction, but `RESEARCH_PROMPT` and `WRITE_PROMPT` are what you actually send, one per turn.
4. **Conversation context is what makes the two-turn pattern work** — Turn 2 doesn't need to restate the research because ADK preserves it.
5. **Non-determinism is expected in agent output** — consistency should be checked via the guardrails in the instruction (and eventually evals), not by expecting identical text on every run.
6. **The trace turns a black box into something inspectable** — you can see the search calls and reasoning that led to the final report, not just the report itself.

---

## Check Your Understanding

Before moving to Lecture 5, you should be able to answer:

1. What has to be set up once per project versus what changes for each new agent?
2. Why doesn't `Turn 2`'s prompt need to repeat the research from `Turn 1`?
3. What's the difference between what `instruction` controls and what `RESEARCH_PROMPT`/`WRITE_PROMPT` control?
4. Why is non-deterministic output expected here, and what should you check for instead of exact repeatability?
5. What can you see in a trace in Arize AX that you couldn't see by only reading the final report?

---

## Summary

Building this agent shows how the pieces from the last three lectures come together in a real system: Google ADK provides the agent and tool framework, the tracing setup from Lecture 3 makes every step observable without extra code, and the two-turn research-then-write pattern demonstrates why conversation context and clear instructions matter more than trying to force identical output on every run. The result is an agent whose behavior you can inspect step-by-step in a trace — which is exactly the foundation the next lecture will build on when we start writing evals against it.
