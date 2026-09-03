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