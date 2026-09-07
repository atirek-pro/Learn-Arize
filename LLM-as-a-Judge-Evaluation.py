import pandas as pd
from dotenv import load_dotenv
from phoenix.evals.llm import LLM
from phoenix.evals import evaluate_dataframe
from openinference.instrumentation import suppress_tracing
from phoenix.evals.metrics import FaithfulnessEvaluator, CorrectnessEvaluator
from phoenix.evals import ClassificationEvaluator

load_dotenv()

llm = LLM(provider="google", model="gemini-flash-latest")

# ---------------------------------------------------------
# 1. Load the Arize CSV files
# ---------------------------------------------------------

all_spans_df = pd.read_csv("arize_all_spans.csv")
parent_spans = pd.read_csv("arize_top_level_spans.csv")


# ---------------------------------------------------------
# 2. Get child spans
# ---------------------------------------------------------

child_spans = all_spans_df[
    all_spans_df["parent_id"].notna()
].copy()


# ---------------------------------------------------------
# 3. Get the final LLM response for each trace
# ---------------------------------------------------------

research_context = {}

for trace_id, group in child_spans.groupby("context.trace_id"):

    # Find spans containing LLM output
    llm_spans = group[
        group["attributes.llm.output_messages"].notna()
    ].copy()

    if len(llm_spans) > 0:

        # Sort chronologically
        llm_spans = llm_spans.sort_values("start_time")

        # Take the final LLM response
        final_response = llm_spans.iloc[-1]

        output = final_response.get(
            "attributes.output.value",
            ""
        )

        if pd.notna(output) and output:
            # Limit context to 5000 characters
            research_context[trace_id] = str(output)[:5000]


# ---------------------------------------------------------
# 4. Add research context to parent spans
# ---------------------------------------------------------

parent_spans["context"] = (
    parent_spans["context.trace_id"].map(research_context)
)


# ---------------------------------------------------------
# 5. Print results
# ---------------------------------------------------------

matched = parent_spans["context"].notna().sum()

print(
    f"Added context to {matched}/{len(parent_spans)} top-level spans"
)

print("\nSample context (first 200 chars):")

if matched > 0:
    first_ctx = parent_spans["context"].dropna().iloc[0]
    print(f"  {first_ctx[:200]}...")
else:
    print("  N/A")


# ---------------------------------------------------------
# 6. Save the updated CSV
# ---------------------------------------------------------

output_file = "arize_top_level_spans_with_context.csv"

parent_spans.to_csv(
    output_file,
    index=False
)

print(f"\nFinal CSV saved as: {output_file}")

# ---------------------------------------------------------
# Correctness Eval
# ---------------------------------------------------------

correctness_eval = CorrectnessEvaluator(llm=llm)

with suppress_tracing():
    correctness_results = evaluate_dataframe(
        dataframe=parent_spans, evaluators=[correctness_eval]
    )
correctness_results.to_csv("correctness_results.csv", index=False)
print("Correctness Evaluation Results saved to correctness_results.csv", "\n")

# ---------------------------------------------------------
# Faithfulness Eval
# ---------------------------------------------------------

faithfulness_eval = FaithfulnessEvaluator(llm=llm)

# Only run on spans that have context
spans_with_context = parent_spans[parent_spans["context"].notna()].copy()

with suppress_tracing():
    faith_results = evaluate_dataframe(
        dataframe=spans_with_context,
        evaluators=[faithfulness_eval]
    )

faith_results.to_csv("faithfulness_results.csv", index=False)
print("Faithfulness Evaluation Results saved to faithfulness_results.csv")
faith_scores = pd.json_normalize(faith_results["faithfulness_score"])
print("Faithfulness results:")
print(f"  {faith_scores['label'].value_counts().to_dict()}")
print(f"\nCorrectness gave us 0/13 passes — not useful for real-time data.")
print(f"Faithfulness gives us a meaningful split — choosing the right eval matters more than tuning it.")

# ---------------------------------------------------------
# Custom Eval
# ---------------------------------------------------------
actionability_template = """
You are an expert financial analyst evaluator. Your task is to judge whether
a financial report provides actionable investment guidance, not just raw data.

ACTIONABLE — The report:
- Contains specific recommendations (buy/sell/hold or equivalent guidance)
- Identifies concrete risks with supporting data
- Includes forward-looking analysis, not just historical data
- Provides context for WHY recommendations are made

NOT ACTIONABLE — The report:
- Only summarizes publicly available data without interpretation
- Lacks specific recommendations or next steps
- Presents risks without supporting evidence
- Contains only backward-looking analysis

Here are examples of each:

Example — ACTIONABLE:
\"Based on NVDA's 122% YoY revenue growth driven by data center demand,
strong forward P/E of 35x relative to sector median of 22x, and expanding
margins, NVDA presents a compelling growth position. Key risk: concentration
in AI training chips (~70% of revenue). Recommendation: accumulate on
pullbacks below $800.\"

Example — NOT ACTIONABLE:
\"NVDA is a major player in the semiconductor industry. The company has seen
significant growth in recent years driven by AI demand. NVDA's stock has
performed well. Investors should consider various factors when making
investment decisions.\"

<user_query>
{input}
</user_query>

<financial_report>
{output}
</financial_report>
"""

# ClassificationEvaluator builds a custom LLM-as-judge evaluator
# from a prompt template. The labels live in `choices`, not the prompt.
actionability_evaluator = ClassificationEvaluator(
    name="actionability",
    llm=llm,
    prompt_template=actionability_template,
    choices={"actionable": 1.0, "not actionable": 0.0},
)

with suppress_tracing():
    action_results_df = evaluate_dataframe(
        dataframe=parent_spans, evaluators=[actionability_evaluator]
    )

action_results_df.to_csv(
    "actionability_results.csv",
    index=False
)

print("Actionability Evaluation Results saved to actionability_results.csv")