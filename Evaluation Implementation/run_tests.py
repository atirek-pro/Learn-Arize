import asyncio

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from FinancialAnalysisAgent.agent import root_agent


# ============================================================
# TEST QUERIES
# ============================================================

test_queries = [
    {"tickers": "AAPL", "focus": "revenue growth and services segment"},
    {"tickers": "NVDA", "focus": "AI chip demand and valuation metrics"},
    {"tickers": "AMZN", "focus": "AWS performance and profitability"},
    {"tickers": "GOOGL", "focus": "advertising revenue and AI strategy"},
    {"tickers": "MSFT", "focus": "cloud computing segment"},
    {"tickers": "META", "focus": "metaverse investments and ad revenue"},
    {"tickers": "TSLA", "focus": "vehicle deliveries and margins"},
    {"tickers": "RIVN", "focus": "financial health and future growth"},
    {"tickers": "AAPL, MSFT", "focus": "comparative financial analysis"},
    {"tickers": "NVDA", "focus": "competitive landscape and market share"},
    {"tickers": "KO", "focus": "dividend yield and stability"},
    {"tickers": "AMZN", "focus": "profitability trends and outlook"},
]


# ============================================================
# ADK CONFIGURATION
# ============================================================

APP_NAME = "FinancialAnalysisAgent"


# ============================================================
# RUN ONE QUERY
# ============================================================

async def run_query(
    runner,
    session_service,
    query,
    query_number,
):
    """
    Run one independent financial analysis.

    A new ADK session is created for every test case so that
    each query represents an independent agent execution.
    """

    user_id = f"test_user_{query_number}"

    prompt = (
        f"Analyze {query['tickers']}, focusing specifically on "
        f"{query['focus']}.\n\n"

        "You must use the yahoo_finance_research tool to retrieve "
        "current financial data and recent financial news before "
        "writing the report.\n\n"

        "After receiving the tool results, analyze the evidence "
        "and write a concise financial analysis report.\n\n"

        "Do not invent financial data. Clearly distinguish "
        "facts retrieved from the tool from your own analysis."
    )

    print("\n" + "=" * 80)
    print(
        f"QUERY {query_number}/{len(test_queries)}"
    )
    print("=" * 80)

    print(f"Ticker(s): {query['tickers']}")
    print(f"Focus:     {query['focus']}")
    print(f"User ID:   {user_id}")

    # --------------------------------------------------------
    # Create a completely new session
    # --------------------------------------------------------

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
    )

    print(f"Session:   {session.id}")

    # --------------------------------------------------------
    # Create user message
    # --------------------------------------------------------

    content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=prompt
            )
        ],
    )

    # --------------------------------------------------------
    # Run agent
    # --------------------------------------------------------

    try:

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):

            if event.is_final_response():

                if event.content and event.content.parts:

                    print("\n" + "-" * 80)
                    print("FINAL REPORT")
                    print("-" * 80)

                    for part in event.content.parts:

                        if part.text:

                            print(part.text)

    except Exception as e:

        print("\n" + "!" * 80)
        print("QUERY FAILED")
        print("!" * 80)

        print(f"Error: {e}")

        # Do not stop the entire experiment because
        # one query failed.
        return


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 80)
    print("GOOGLE ADK + YAHOO FINANCE TOOL EXPERIMENT")
    print("=" * 80)

    print()
    print(f"Total test queries: {len(test_queries)}")
    print(f"App name:           {APP_NAME}")
    print()

    # --------------------------------------------------------
    # Session service
    # --------------------------------------------------------

    session_service = InMemorySessionService()

    # --------------------------------------------------------
    # Runner
    # --------------------------------------------------------

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # --------------------------------------------------------
    # Execute sequentially
    # --------------------------------------------------------

    for i, query in enumerate(
        test_queries,
        start=1,
    ):

        await run_query(
            runner=runner,
            session_service=session_service,
            query=query,
            query_number=i,
        )

        # Small separation between experiments
        await asyncio.sleep(1)

    print("\n")
    print("=" * 80)
    print("ALL TEST QUERIES COMPLETED")
    print("=" * 80)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())