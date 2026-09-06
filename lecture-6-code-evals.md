# Lecture 6: Code Evals

> **Learning objective:** Build, run, and log your first real eval — a deterministic code eval that checks whether a financial agent's output mentions every ticker the user asked about — and understand the design principle that makes it trustworthy: grading the outcome, not the path.

This lecture's reference implementation runs as a **Google Colab notebook**, pulling exported spans from Arize AX as a CSV. If you're adapting this into a local script instead (like the `agent.py` files from Lectures 3–4), swap the hardcoded credential variables for `os.environ` + `load_dotenv()`, the same pattern used there.

---

## 1. The Simplest Useful Eval

Back in Lecture 2, a **code eval** was defined as a deterministic, code-based check — no second model involved in grading. This lecture builds the simplest version of one that's actually useful in production: a check that the agent's financial report **mentions every ticker symbol the user asked about.**

This is a good first eval precisely because it's simple: no LLM-as-a-judge, no subjective rubric, just a yes/no structural check. But "simple" doesn't mean "trivial" — dropping a requested ticker from a financial report is a real, meaningful failure, not a cosmetic one.

---

## 2. Setup: Install Dependencies and Import

```python
!pip install pandas arize arize-phoenix arize-otel openinference-instrumentation-google-adk
```

```python
import re
import os
import pandas as pd

from google.colab import drive

from phoenix.evals import create_evaluator
from phoenix.evals import evaluate_dataframe

from openinference.instrumentation import suppress_tracing

from arize import ArizeClient
```

Two new pieces here beyond what Lectures 3–4 installed:

- **`arize-phoenix`** provides the eval framework itself — `create_evaluator` (defines an eval) and `evaluate_dataframe` (runs it against a batch of data).
- **`arize`** (`ArizeClient`) is the client used to talk to Arize AX directly — not just to send traces (as in Lecture 3–4), but to read spans back out and write eval results onto them.

---

## 3. Get Your Spans from AX

Before you can evaluate anything, you need the traces you set up in Lecture 3–4 pulled out as data you can loop over. That happens in two stages: first, a separate export step pulls spans out of Arize AX and saves them as CSVs; then, the eval notebook (Section 2) loads that CSV to run against.

> **On credentials:** every credential shown below is a placeholder. Never commit or paste a real API key into a notebook, script, or chat — treat one as compromised the moment it's been shared anywhere outside a secrets manager or `.env` file, and rotate it in your Arize AX account settings if it has been.

### 3.1 Export Spans from Arize AX to CSV

This part runs as its own notebook, separate from the eval notebook — its only job is to pull spans down and save them locally so the eval step has something to load.

**Install and mount Drive:**

```python
!pip install -q -U arize pandas
```

```python
from google.colab import drive
drive.mount("/content/drive")
```

**Configure and validate credentials:**

```python
import os
import pandas as pd

# ------------------------------------------------------------
# ARIZE CONFIGURATION
# ------------------------------------------------------------

ARIZE_API_KEY = "<YOUR-ARIZE-API-KEY>"
SPACE_ID = "<YOUR-SPACE-ID>"

# IMPORTANT:
# This must match the project_name used in agent.py
PROJECT_NAME = "FinancialAnalysisAgent"

# Folder inside Google Drive
OUTPUT_FOLDER = "/content/drive/MyDrive/arize_traces"


# ------------------------------------------------------------
# Validate credentials
# ------------------------------------------------------------

if not ARIZE_API_KEY:
    raise ValueError(
        "ARIZE_AX_API_KEY environment variable is not set."
    )

if not SPACE_ID:
    raise ValueError(
        "ARIZE_AX_SPACE_ID environment variable is not set."
    )
```

`PROJECT_NAME` isn't arbitrary — it has to exactly match the `project_name="google_adk"`-style value passed into `register(...)` back in Lecture 3–4's `agent.py`. This is the string that tells Arize AX which project's spans to pull.

**Connect to Arize:**

```python
from arize import ArizeClient

arize_client = ArizeClient(
    api_key=ARIZE_API_KEY
)

print("Connected to Arize client.")
```

**Fetch spans for a time window:**

```python
from datetime import datetime, timedelta, timezone

end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=7)

print(f"Project:    {PROJECT_NAME}")
print(f"Start time: {start_time}")
print(f"End time:   {end_time}")

try:
    spans_df = arize_client.spans.export_to_df(
        space_id=SPACE_ID,
        project_name=PROJECT_NAME,
        start_time=start_time,
        end_time=end_time,
    )
except Exception as e:
    print("ERROR FETCHING SPANS")
    print(str(e))
    raise

print(f"Total spans fetched from Arize: {len(spans_df)}")
```

`export_to_df` pulls back **every** span in the window — every model call, every tool call, every reasoning step (Lecture 2's spans) — not just one row per conversation. `spans_df` at this point is the raw trace data, unfiltered.

**Save the full export:**

```python
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

all_spans_file = os.path.join(OUTPUT_FOLDER, "arize_all_spans.csv")
spans_df.to_csv(all_spans_file, index=False)

print("ALL SPANS SAVED:", all_spans_file)
```

**Filter down to top-level (root) spans:**

The ticker eval only needs the *overall* input and output of each conversation, not every intermediate tool call inside it — that's the top-level (root) span of each trace, identifiable as the one with no parent:

```python
if "parent_id" not in spans_df.columns:
    raise ValueError(
        "The exported Arize data does not contain a 'parent_id' "
        "column. Cannot reliably identify top-level spans."
    )

# Treat these as "no parent": NaN, None, "", whitespace-only,
# or the literal strings "None"/"nan" left over from CSV export.
spans_df["parent_id"] = (
    spans_df["parent_id"].astype("string").str.strip()
)

no_parent_mask = (
    spans_df["parent_id"].isna()
    | spans_df["parent_id"].eq("")
    | spans_df["parent_id"].eq("None")
    | spans_df["parent_id"].eq("nan")
)

top_level_spans = spans_df[no_parent_mask].copy()

print(f"Total spans fetched:      {len(spans_df)}")
print(f"Top-level spans found:    {len(top_level_spans)}")
print(f"Child spans filtered out: {len(spans_df) - len(top_level_spans)}")
```

The four-way check on `parent_id` is deliberately defensive: a value round-tripped through a CSV export can end up as a true null, an empty string, or the literal text `"None"`/`"nan"` depending on how it was serialized — checking only one of those would silently miss root spans that happen to be represented differently.

**Normalize column names for the evaluator:**

Raw exports store text under Arize's own attribute naming, but `mentions_requested_tickers` (Section 4) expects plain `input`/`output` columns — so this step bridges the two:

```python
if "input" not in top_level_spans.columns:
    if "attributes.input.value" in top_level_spans.columns:
        top_level_spans.rename(
            columns={"attributes.input.value": "input"},
            inplace=True,
        )

if "output" not in top_level_spans.columns:
    if "attributes.output.value" in top_level_spans.columns:
        top_level_spans.rename(
            columns={"attributes.output.value": "output"},
            inplace=True,
        )

# Remove duplicate column names
top_level_spans = top_level_spans.loc[
    :, ~top_level_spans.columns.duplicated()
]
```

**Save the top-level spans CSV:**

```python
top_level_file = os.path.join(OUTPUT_FOLDER, "arize_top_level_spans.csv")
top_level_spans.to_csv(top_level_file, index=False)

print("TOP-LEVEL SPANS SAVED:", top_level_file)
```

This `arize_top_level_spans.csv` file is exactly the file the eval notebook loads in Section 3.2 below.

**Sanity-check the export before moving on:** it's worth confirming the export actually captured what you expect before building an eval on top of it — a trace summary (unique trace count), a breakdown of `attributes.openinference.span.kind` values, and a check for `TOOL`-kind spans specifically (a project with zero tool spans found is a sign something's wrong with instrumentation, not just an empty result worth ignoring). If you want a local copy instead of just Google Drive, `from google.colab import files` followed by `files.download(top_level_file)` downloads it directly from the Colab session.

### 3.2 Load the CSV for Evaluation

With `arize_top_level_spans.csv` saved, the eval notebook from here just needs to mount Drive and read it in:

```python
drive.mount("/content/drive")
```

```python
CSV_PATH = "/content/drive/MyDrive/arize_top_level_spans.csv"
```

```python
SPACE_ID = "<YOUR-SPACE-ID>"
PROJECT_NAME = "<PROJECT-NAME>"
```

```python
ARIZE_API_KEY = "<YOUR-ARIZE-API>"
```

```python
if not ARIZE_API_KEY:
    raise ValueError(
        "ARIZE_API_KEY is not set. "
        "Set it using a Colab Secret or os.environ."
    )

arize_client = ArizeClient(
    api_key=ARIZE_API_KEY
)
```

```python
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(
        f"CSV file not found:\n{CSV_PATH}\n\n"
        "Check the path in Google Drive."
    )

parent_spans = pd.read_csv(CSV_PATH)

print("CSV loaded successfully!")
print(f"Rows: {len(parent_spans)}")
print(f"Columns: {len(parent_spans.columns)}")
```

> **Colab vs. local script:** here, credentials are set as plain variables (or better, a Colab Secret) rather than a `.env` file, because that's the standard pattern in a notebook environment. The underlying idea is the same as Lecture 3's `os.getenv(...)` calls — don't hardcode real keys directly into a file you might commit or share.

`parent_spans` is now a DataFrame where each row is one top-level trace — the same traces you'd otherwise be reading one-by-one in the Arize AX UI (Lecture 5), now available in bulk.

---

## 4. The Ticker Check Eval

### Extracting the requested tickers

The agent's input isn't a clean list of tickers — it's a natural-language prompt (recall `RESEARCH_PROMPT` from Lecture 4: *"Research {tickers}. Focus on: {focus}..."*). Before checking anything, you need to pull the actual ticker symbols out of that text:

```python
TICKER_EXCLUSIONS = {
    "AI",
    "US",
    "CEO",
    "CFO",
    "IPO",
    "ETF",
    "AWS",
    "USE",
    "NYSE",
    "NASDAQ",
}
```

```python
def extract_tickers(text: str) -> list[str]:
    """
    Extract likely stock tickers from the user input.

    Handles prompts such as:
        Analyze AAPL...
        Analyze AAPL, MSFT...
        Analyze NVDA...
    """

    if not text:
        return []

    # Look for the actual user request inside the ADK invocation.
    # This prevents session IDs / JSON fields from influencing extraction.
    match = re.search(
        r'"text"\s*:\s*"Analyze\s+([^"]+?)\s*,?\s*focusing',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        ticker_section = match.group(1)
    else:
        # Fallback for plain-text inputs.
        match = re.search(
            r"Analyze\s+(.+?)(?:,?\s*focusing|$)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        ticker_section = match.group(1) if match else text

    # Extract uppercase ticker-like tokens.
    candidates = re.findall(r"\b[A-Z]{1,5}\b", ticker_section.upper())

    # Preserve order while removing duplicates.
    tickers = []
    for ticker in candidates:
        if ticker not in TICKER_EXCLUSIONS and ticker not in tickers:
            tickers.append(ticker)

    return tickers
```

Two details worth noticing:

- The regex specifically targets the `"text": "Analyze ..."` field inside the raw ADK span data, rather than scanning the whole raw input blob — otherwise session IDs or unrelated JSON keys could get matched as if they were tickers.
- `TICKER_EXCLUSIONS` exists because 1–5 letter uppercase words are common in financial writing that *aren't* tickers ("CEO", "IPO", "NYSE"). Without this list, the eval would generate false positives on requested tickers that were never actually asked for.

### The evaluator itself

```python
@create_evaluator(
    name="mentions_requested_tickers",
    kind="code"
)
def mentions_requested_tickers(input, output):
    """
    Checks whether the financial analysis mentions
    every ticker requested by the user.
    """

    if not input or not output:
        return {
            "label": "unknown",
            "score": 0,
            "explanation": "Missing input or output.",
        }

    requested_tickers = extract_tickers(str(input))

    if not requested_tickers:
        return {
            "label": "unknown",
            "score": 0,
            "explanation": (
                "Could not identify a ticker in the input."
            ),
        }

    output_text = str(output).upper()

    missing_tickers = [
        ticker
        for ticker in requested_tickers
        if not re.search(rf"\b{re.escape(ticker)}\b", output_text)
    ]

    if not missing_tickers:
        return {
            "label": "pass",
            "score": 1,
            "explanation": (
                "All requested tickers were mentioned: "
                f"{', '.join(requested_tickers)}."
            ),
        }

    return {
        "label": "fail",
        "score": 0,
        "explanation": (
            f"Missing tickers: {', '.join(missing_tickers)}. "
            f"Requested: {', '.join(requested_tickers)}."
        ),
    }
```

`@create_evaluator(kind="code")` registers this function as a code eval Phoenix can run at scale. Notice the return shape is always the same three fields — `label`, `score`, `explanation` — regardless of which branch runs. That consistency is what makes results from many different evals combinable later (Section 5 and 7 rely on this structure).

Also notice the deliberate **`"unknown"`** label, distinct from `"pass"`/`"fail"`. If the extractor couldn't find a ticker in the input at all, that's not the same as the agent failing — it means the eval itself couldn't make a judgment, and that ambiguity shouldn't be silently counted as a pass or a fail.

---

## 5. Run the Ticker Check

```python
print("\nRunning evaluation...")

with suppress_tracing():

    results = evaluate_dataframe(
        dataframe=parent_spans,
        evaluators=[
            mentions_requested_tickers
        ],
    )

print("Evaluation completed!")
```

`suppress_tracing()` matters here: without it, running the evaluation itself — which may call other instrumented code — could generate *new* trace spans in Arize AX, polluting your data with noise from the evaluation process itself rather than the agent's actual behavior.

```python
ticker_scores = pd.json_normalize(
    results["mentions_requested_tickers_score"]
)

print("\nMentions Ticker Results:")

label_counts = (
    ticker_scores["label"]
    .value_counts()
    .to_dict()
)

passed = label_counts.get("pass", 0)
total = len(ticker_scores)

print(f"  {label_counts}")
print(f"  {passed}/{total} passed")
```

This gives you the first useful number: how many traces passed out of the total — the kind of consistent, repeatable measurement Lecture 5's "Swiss Cheese" model credits to automated evals specifically.

---

## 6. What the Failing Traces Revealed

Passing/failing counts alone don't tell you *why* something failed — which is why every eval result here carries an `explanation`, not just a score:

```python
failures = ticker_scores[
    ticker_scores["label"] != "pass"
]

if len(failures) > 0:

    print("\nIssues:")

    for _, row in failures.iterrows():

        print(
            f"  {row.get('explanation', 'no explanation')}"
        )

else:

    print("\nAll passed!")
```

This is where Lecture 5's reading practice and Lecture 6's automated eval meet: instead of manually reading every trace to find the ones where a ticker got dropped, the eval surfaces exactly those failing cases with an explanation already attached — for example, a report that covered `AAPL` in depth but never mentioned `MSFT` at all, even though both were requested. That's a concrete, root-causeable finding (Lecture 5, Section 6) — likely a **scope** or **reasoning** issue, not a hallucination — rather than a vague "sometimes it's wrong."

---

## 7. Log the Results Back to AX

An eval that only prints to a notebook doesn't help anyone monitoring the system in Arize AX. The last step writes these results back onto the original spans, as annotations:

```python
def log_eval_to_ax(
    eval_results_df,
    eval_name
):
    """
    Send evaluation results back to the
    corresponding spans in Arize AX.
    """

    annotations = pd.DataFrame({
        "context.span_id": eval_results_df["context.span_id"],

        f"eval.{eval_name}.label": eval_results_df[
            f"{eval_name}_score"
        ].apply(
            lambda x: x.get("label") if isinstance(x, dict) else None
        ),

        f"eval.{eval_name}.score": eval_results_df[
            f"{eval_name}_score"
        ].apply(
            lambda x: x.get("score") if isinstance(x, dict) else None
        ),

        f"eval.{eval_name}.explanation": eval_results_df[
            f"{eval_name}_score"
        ].apply(
            lambda x: x.get("explanation", "") if isinstance(x, dict) else ""
        ),
    })

    # Ensure AX-compatible data types
    annotations[f"eval.{eval_name}.label"] = (
        annotations[f"eval.{eval_name}.label"].fillna("").astype(str)
    )

    annotations[f"eval.{eval_name}.score"] = pd.to_numeric(
        annotations[f"eval.{eval_name}.score"], errors="coerce"
    )

    annotations[f"eval.{eval_name}.explanation"] = (
        annotations[f"eval.{eval_name}.explanation"].fillna("").astype(str)
    )

    print("\nAnnotations being sent to AX:")
    print(annotations.to_string(index=False))

    print("\nAnnotation columns:")
    print(annotations.columns.tolist())

    print("\nUploading evaluations to Arize AX...")

    arize_client.spans.update_evaluations(
        space_id=SPACE_ID,
        project_name=PROJECT_NAME,
        dataframe=annotations,
    )

    print(f"\nLogged {len(annotations)} {eval_name} evaluations to AX")
```

```python
print("\nFinal evaluation results:")

print(
    results[
        [
            "context.trace_id",
            "context.span_id",
            "mentions_requested_tickers_score",
        ]
    ].to_string(index=False)
)

log_eval_to_ax(
    results,
    "mentions_requested_tickers",
)
```

Two things worth understanding about `log_eval_to_ax`:

- **`context.span_id` is the join key.** It's how a locally-computed eval result gets attached back to the *exact* trace it was graded from, instead of just existing as a disconnected spreadsheet.
- **The type coercion step isn't boilerplate you can skip.** Arize AX expects consistent types per column (`label` as a string, `score` as a number) — a mixed-type column (some `None`, some numeric, some string) would fail to upload cleanly, so nulls are filled and types are explicitly cast before the upload call.

---

## 8. Why This Matters

Once this eval is logged, every trace in your Arize AX project carries a `pass`/`fail`/`unknown` label for "did this report mention every ticker asked for" — visible and filterable right alongside the trace itself. That turns Lecture 5's manual practice (read a dozen traces, notice what's broken) into something that runs automatically over *every* trace, repeatably, going forward.

This is also a small-scale, concrete example of the CI quality gate described in Lecture 1: if this eval ran as part of a deployment pipeline instead of a notebook, a drop in the pass rate after a prompt change would be a signal to block the release — exactly the "detect regressions when you change a prompt" use case from Lecture 1, made real.

---

## 9. Code Evals Aren't Just Toys

A ticker-mention check might look narrow, but the same pattern — deterministic, structural, fast — covers a wide range of genuinely important checks. A few more examples in the same style:

**Did the output parse as valid JSON?**
```python
import json

def is_valid_json(output: str) -> bool:
    try:
        json.loads(output)
        return True
    except (json.JSONDecodeError, TypeError):
        return False
```

**Is the response under a length limit?**
```python
def is_under_token_limit(output: str, max_tokens: int = 500) -> bool:
    # simple whitespace-based approximation
    return len(output.split()) <= max_tokens
```

**Does it avoid forbidden phrases?**
```python
FORBIDDEN_PHRASES = ["guaranteed returns", "risk-free"]

def avoids_forbidden_phrases(output: str) -> bool:
    text = output.lower()
    return not any(phrase in text for phrase in FORBIDDEN_PHRASES)
```

None of these need a model to grade them, none of them are expensive to run, and all of them can run on every single output in production. That combination — cheap, fast, deterministic — is exactly why code evals are a foundation to build on, not a beginner exercise to move past.

---

## 10. Grade the Outcome, Not the Path

Look back at `mentions_requested_tickers`: it never checks *how* the agent found its information — which search queries it ran, how many tool calls it made, what order it reasoned in. It only checks the **final output**: are the requested tickers mentioned or not.

This is a deliberate design choice, not a limitation. As Lecture 2 covered (Section 8, "Creatively correct vs. wrong"), **agents find valid approaches you didn't anticipate.** An eval that asserts on a specific trajectory — "it must call `google_search` exactly twice," "it must search for the ticker before the company name" — will fail an agent that solved the problem correctly through a different, equally valid path. That's a false negative baked directly into the eval's design.

Checking the **outcome** instead of the **trajectory** keeps the eval robust to legitimate variation in how the agent gets there, while still catching the failure that actually matters: a ticker the user asked about that never shows up in the final report.

---

## Key Takeaways

1. **A code eval doesn't need an LLM to be useful** — a deterministic structural check can catch real, meaningful failures.
2. **Extracting clean signal from messy input is half the work** — the ticker-extraction regex and exclusion list exist entirely to avoid false positives before the actual check even runs.
3. **`suppress_tracing()` keeps evaluation runs from polluting your trace data** with spans generated by the evaluation process itself.
4. **An explanation attached to every result is what makes failures actionable** — a plain pass/fail count alone doesn't tell you what to fix.
5. **Logging results back onto the original spans (via `context.span_id`) is what turns an eval from a one-off notebook run into ongoing observability** inside Arize AX.
6. **Code evals generalize far beyond one example** — JSON validity, length limits, and forbidden-phrase checks all follow the same cheap, deterministic pattern.
7. **Grade the outcome, not the path** — checking the final result instead of the exact steps taken avoids penalizing an agent for finding a different, equally valid way to succeed.

---

## Check Your Understanding

Before moving to Lecture 7, you should be able to answer:

1. Why is a ticker-mention check a good *first* eval to build, rather than starting with an LLM-as-a-judge eval?
2. Why does `extract_tickers` need an exclusion list like `TICKER_EXCLUSIONS`?
3. What does `suppress_tracing()` prevent, and why does it matter here specifically?
4. Why does the evaluator return an `"unknown"` label instead of just `"pass"` or `"fail"` when it can't identify a ticker?
5. What role does `context.span_id` play in `log_eval_to_ax`?
6. Why is type coercion (`astype(str)`, `pd.to_numeric`) a necessary step before uploading annotations, not just cleanup?
7. Why would asserting on the agent's exact tool-call sequence be a worse eval design than checking the final output?

---

## Summary

This lecture turns the reading practice from Lecture 5 into something automated: a deterministic eval that checks a real, meaningful property of the agent's output — whether every requested ticker actually shows up in the report — runs it across every trace at once, and logs the results back onto those exact spans in Arize AX. The design principle underneath it generalizes well beyond this one check: code evals are cheap, fast, and genuinely useful for anything structurally checkable, and they hold up best when they grade what the agent produced rather than the specific path it took to produce it.
