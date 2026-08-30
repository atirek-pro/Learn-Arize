import os
from dotenv import load_dotenv
from arize.otel import register
from google.adk.agents.llm_agent import Agent
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


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city."""
    return {
        "status": "success",
        "city": city,
        "time": "10:30 AM"
    }


root_agent = Agent(
    model="gemini-flash-latest",
    name="root_agent",
    description="Tells the current time in a specified city.",
    instruction=(
        "You are a helpful assistant that tells the current time in cities. "
        "Use the 'get_current_time' tool for this purpose."
    ),
    tools=[get_current_time],
)