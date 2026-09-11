import re
from dotenv import load_dotenv
import pandas as pd
from phoenix.evals import create_evaluator
from phoenix.evals import evaluate_dataframe
from phoenix.evals.utils import to_annotation_dataframe
from openinference.instrumentation import suppress_tracing
from arize import ArizeClient
import os

load_dotenv()

arize_client = ArizeClient(api_key=os.environ["ARIZE_AX_API_KEY"])
SPACE_ID = os.environ["ARIZE_AX_SPACE_ID"]
PROJECT_NAME = "FinancialAnalysisAgent"
parent_spans = pd.read_csv("arize_top_level_spans.csv")

# Common uppercase words that can appear in financial prompts
# but are not stock tickers.
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


@create_evaluator(name="mentions_requested_tickers", kind="code")
def mentions_requested_tickers(input, output):
    """
    Code evaluator:
    Checks whether the financial analysis mentions every ticker
    requested by the user.
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
            "explanation": "Could not identify a ticker in the input.",
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
                f"All requested tickers were mentioned: "
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


# Run evaluation without generating additional traces.
with suppress_tracing():
    results = evaluate_dataframe(
        dataframe=parent_spans,
        evaluators=[mentions_requested_tickers],
    )

# print("\nRESULT COLUMNS:")
# print(results.columns.tolist())

# print("\nRESULT SHAPE:")
# print(results.shape)

# print("\nRESULT SAMPLE:")
# print(results.head().to_string())

# Show ticker evaluation results
ticker_scores = pd.json_normalize(
    results["mentions_requested_tickers_score"]
)

print("Mentions Ticker Results:")

label_counts = ticker_scores["label"].value_counts().to_dict()
passed = label_counts.get("pass", 0)
total = len(ticker_scores)

print(f"  {label_counts}")
print(f"  {passed}/{total} passed")

# Show failures with explanations
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

def log_eval_to_ax(eval_results_df, eval_name):
    """
    Send Phoenix evaluation results back to the corresponding
    spans in Arize AX.
    """

    annotations = pd.DataFrame({
        "context.span_id": eval_results_df["context.span_id"],
        f"eval.{eval_name}.label": eval_results_df[
            f"{eval_name}_score"
        ].apply(lambda x: x.get("label") if isinstance(x, dict) else None),
        f"eval.{eval_name}.score": eval_results_df[
            f"{eval_name}_score"
        ].apply(lambda x: x.get("score") if isinstance(x, dict) else None),
        f"eval.{eval_name}.explanation": eval_results_df[
            f"{eval_name}_score"
        ].apply(lambda x: x.get("explanation", "") if isinstance(x, dict) else ""),
    })

    # Ensure AX-compatible types
    annotations[f"eval.{eval_name}.label"] = (
        annotations[f"eval.{eval_name}.label"]
        .fillna("")
        .astype(str)
    )

    annotations[f"eval.{eval_name}.score"] = pd.to_numeric(
        annotations[f"eval.{eval_name}.score"],
        errors="coerce",
    )

    annotations[f"eval.{eval_name}.explanation"] = (
        annotations[f"eval.{eval_name}.explanation"]
        .fillna("")
        .astype(str)
    )

    print("\nAnnotations being sent to AX:")
    print(annotations.to_string(index=False))

    print("\nAnnotation columns:")
    print(annotations.columns.tolist())

    # Upload evaluations
    arize_client.spans.update_evaluations(
        space_id=SPACE_ID,
        project_name=PROJECT_NAME,
        dataframe=annotations,
    )

    print(
        f"\nLogged {len(annotations)} "
        f"{eval_name} evaluations to AX"
    )

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