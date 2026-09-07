# Lecture 3: Set Up Tracing with Arize AX

> **Learning objective:** Set up a Google ADK agent project and connect it to Arize AX so every request is automatically traced — and understand *why* the setup works, not just what commands to run.

---

## 1. What Is Arize AX?

Arize AX is a **hosted AI observability platform**. In practical terms, three things about it matter for this lecture:

- It **captures traces** from an AI application — the spans covered in Lecture 2 (model calls, tool calls, reasoning steps).
- It's **framework-agnostic** — it can capture traces from any AI framework, not just one.
- It's **built for production** — designed to observe systems handling real traffic, not just local debugging.

In this lecture, we'll connect it to an agent built with **Google ADK** (Agent Development Kit), but the same core pattern — install an instrumentor, register a trace provider, run your app — applies regardless of which framework you're using.

---

## 2. Get Your Arize AX Credentials

Before writing any code, you need an account and two credentials.

1. Go to **arize.com** and start a free trial.
2. Once logged in, go to **Settings** and copy two values:
   - Your **API Key**
   - Your **Space ID**

You'll need both in Section 4 — they're what tell Arize AX *which account and which project* to send your traces to.

---

## 3. Install Dependencies

For a Google ADK project, you need three packages:

```bash
pip install arize-otel
pip install openinference-instrumentation-google-adk
pip install google-adk
```

**What each one does:**

| Package | Role |
|---|---|
| `arize-otel` | Sends traces from your app to Arize AX, using the OpenTelemetry standard |
| `openinference-instrumentation-google-adk` | Auto-instruments Google ADK specifically — it knows how to turn ADK's internal agent/tool calls into trace spans |
| `google-adk` | The agent framework itself |

> **Note on the package name:** if you're pulling this from other notes or docs, double-check you're installing the **ADK-specific** instrumentation package (`openinference-instrumentation-google-adk`), not a generic Gemini/`google-genai` one — the code in Section 5 imports `GoogleADKInstrumentor`, which comes from the ADK package, not the genai one. Installing the wrong instrumentor will leave your ADK-specific calls untracked even though the import might look similar.

---

## 4. Store Your Credentials

The code in the next section reads your API key and Space ID from environment variables, so create a `.env` file in your project root:

```bash
ARIZE_AX_SPACE_ID=your-space-id-here
ARIZE_AX_API_KEY=your-api-key-here
```

Keeping credentials in `.env` (instead of hardcoding them) means you can commit your agent code without leaking your API key.

---

## 5. Create the Google ADK Project

Scaffold a new agent project with the ADK CLI:

```bash
adk create my_agent
```

This generates a project folder with an `agent.py` file. The only element ADK actually requires is a `root_agent` definition — everything else (tools, instructions, model choice) is configuration on top of that.

---

## 6. Instrument the Agent

Open `agent.py` and update it to both **define the agent** and **wire up tracing**:

```python
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
```

**Walking through what each part does:**

- `load_dotenv()` pulls your Space ID and API key from the `.env` file into the environment.
- `register(...)` creates a **trace provider** — the object responsible for collecting spans and shipping them to your Arize AX project (`project_name="google_adk"` is what groups these traces together in the Arize AX dashboard).
- `GoogleADKInstrumentor().instrument(tracer_provider=trace_provider)` is the step that actually turns on tracing — it patches into ADK's internals so that every agent run, tool call, and reasoning step automatically emits a span to the trace provider you just created.
- `get_current_time` is a plain Python function turned into a **tool** the agent can call — this is one of the things that will now show up as its own span in every trace.
- `root_agent` is the required piece: it ties together the model, instructions, and available tools into a working agent.

Notice that nothing in `get_current_time` or in the agent's instructions had to change to support tracing — instrumentation is entirely handled by the four lines above the tool definition.

---

## 7. Run the Agent

```bash
adk run my_agent
```

This starts the agent from the command line. Every request you send it now flows through the instrumented code path — meaning it's automatically traced and shipped to Arize AX with no extra work per-request.

---

## 8. Why This Works So Smoothly

The reason this setup is just "install two packages, add a few lines, run" comes down to **auto-instrumentation**:

- `GoogleADKInstrumentor` already knows the internal structure of a Google ADK agent — where a model call happens, where a tool call happens, where a response gets returned. It doesn't need you to manually mark each of these; it hooks into ADK's own code paths and generates spans automatically.
- `register()` and the instrumentor both speak **OpenTelemetry**, an open standard for traces — that's *why* `arize-otel` can receive spans from an ADK-specific instrumentor without the two needing custom code to talk to each other.
- Because instrumentation happens once, at startup (`.instrument(...)`), rather than per-request, you don't have to add tracing code to every tool or agent you write afterward — new tools you add to `root_agent` are traced automatically, the same way `get_current_time` is here.

This connects directly back to Lecture 2: this is *how* spans (Lecture 2, Section 2) actually get generated in a real system. You're not manually logging each step — the instrumentor is generating the trace structure for you, from a framework it already understands.

---

## Key Takeaways

1. **Arize AX is framework-agnostic** — the same register-and-instrument pattern applies beyond Google ADK.
2. **Tracing setup is credential + instrumentation**, not custom logging code — you install an instrumentor built for your framework and register a trace provider, rather than writing trace/span code by hand.
3. **`register()` connects your app to your Arize AX project**; `Instrumentor().instrument()` is what actually turns tracing on.
4. **Match the instrumentation package to your framework** — an ADK app needs the ADK-specific instrumentor, not a generic model-provider one.
5. **Instrumentation happens once, at startup** — every tool and agent call afterward is traced automatically, without per-call tracing code.
6. **This is the practical mechanism behind spans** from Lecture 2 — auto-instrumentation is what generates them in a real running system.

---

## Check Your Understanding

Before moving to Lecture 4, you should be able to answer:

1. What are the two credentials you need from Arize AX, and where do you get them?
2. What does `register()` do, versus what `GoogleADKInstrumentor().instrument()` does?
3. Why does the instrumentation package need to match your specific framework?
4. Why don't you need to add tracing code inside `get_current_time` itself?
5. What underlying standard lets `arize-otel` and a framework-specific instrumentor work together?
6. How does this setup connect to the concept of spans from Lecture 2?

---

## Summary

Setting up tracing with Arize AX for a Google ADK agent comes down to three moving parts: credentials that identify where traces should go, a trace provider that collects them, and a framework-specific instrumentor that knows how to turn your agent's internal behavior into spans automatically. Because all of this is built on the OpenTelemetry standard, the setup stays small — a handful of lines — while giving you full visibility into every model call, tool call, and reasoning step your agent makes, with no manual logging required.
