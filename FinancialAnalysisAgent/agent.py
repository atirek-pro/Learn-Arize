"""
We're building a financial analysis chatbot using the Google ADK SDK.

The agent works in two turns:

Turn 1: Research — searches the web for real financial data
Turn 2: Write — compiles the research into a readable report

The Agent maintains conversation context between turns, so the writer
has access to the researcher's findings.
"""
import os
from dotenv import load_dotenv
from arize.otel import register

from google.adk.agents import Agent
from google.adk.tools import google_search
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

load_dotenv()

trace_provider = register(
    space_id=os.getenv("ARIZE_AX_SPACE_ID"),
    api_key=os.getenv("ARIZE_AX_API_KEY"),
    project_name="google_adk"
)

# Instrument Google ADK
GoogleADKInstrumentor().instrument(
    tracer_provider=trace_provider
)

RESEARCH_PROMPT = """Research {tickers}. Focus on: {focus}.
Use web search to find current financial data, news, and trends."""


WRITE_PROMPT = """Now write a concise financial report based on your research above."""


root_agent = Agent(
    name="financial_report_agent",
    model="gemini-flash-latest",
    description=(
        "An agent that researches financial information using web search "
        "and writes concise financial reports."
    ),
    instruction=(
        "You are a financial analysis agent.\n\n"
        
        "When the user asks for a financial report, follow this workflow:\n\n"
        
        "1. RESEARCH\n"
        "   - Identify the requested ticker symbols.\n"
        "   - Identify the user's requested focus.\n"
        "   - Use web search to find current financial data, relevant news, "
        "and market trends.\n"
        "   - Base your analysis on current, reliable information.\n\n"
        
        "2. WRITE\n"
        "   - Use the research gathered above.\n"
        "   - Write a concise and readable financial report.\n"
        "   - Clearly distinguish factual information from analysis or outlook.\n"
        "   - Do not invent financial data.\n\n"
        
        "Maintain the research findings in the current conversation context "
        "so they can be used when writing the final report."
    ),
    tools=[google_search],
)