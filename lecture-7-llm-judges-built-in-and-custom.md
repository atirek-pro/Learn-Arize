# Lecture 7: LLM Judges — Built-In and Custom

> **Learning objective:** Understand when code evals aren't enough, run Arize AX's built-in LLM-judge evaluators (Correctness, Faithfulness), and build a well-structured custom rubric for judgments no built-in eval covers — like whether a financial report is actually *actionable*.

This lecture picks up exactly where Lecture 6 left off: `arize_all_spans.csv` and `arize_top_level_spans.csv`, the two files exported in Lecture 6's Section 3.1, are the starting point here.

---

## 1. What Code Can't Check

Lecture 6's ticker-mention eval could only ever be a *structural* check — did a specific string appear in the output. It has no way to judge whether a financial report is well-reasoned, whether its claims are actually grounded in the research the agent did, or whether it gives the user something they can act on. Those are questions about **meaning**, and meaning is exactly what code evals (Lecture 2, Section 3) can't grade. That's the gap **LLM-as-a-judge** evals exist to fill.

---

## 2. Three Components of an LLM Judge

Every LLM judge, built-in or custom, is made of the same three pieces:

1. **A judge model** — the LLM doing the grading (not the agent being graded).
2. **A rubric** — the criteria it's applying to make that judgment.
3. **Data** — the examples being evaluated.

Keeping these three separate matters: the judge model can change (a cheaper or better model), the rubric can be tuned, and the data can grow — independently of one another. Confusing "the rubric" with "the data" (or hardcoding one into the other) is exactly what Section 9's "keep choices out of the prompt" rule is protecting against later in this lecture.

---

## 3. AX Ships Built-In Evals

Arize AX provides a set of ready-made LLM judges, meaning you don't have to write a rubric from scratch for the most common judgments:

- **Correctness**
- **Faithfulness**
- **Conciseness**
- **Tool Selection**
- **Tool Invocation**
- **Document Relevance**
- **Refusal**

These ship with their rubric already engineered — **no prompt engineering required** to use them. This lecture uses two of them, Correctness and Faithfulness, and shows why picking the *right* one mattered more here than trying to tune either.

---

## 4. Building Context: What Faithfulness Needs

Before running any judge, the code loads the two CSVs from Lecture 6 and reconstructs one piece of data that doesn't already exist in the top-level export: the actual research the agent gathered, which becomes the **context** column faithfulness checking depends on.

```python
import pandas as pd
from dotenv import load_dotenv
from phoenix.evals.llm import LLM
from phoenix.evals import evaluate_dataframe
from openinference.instrumentation import suppress_tracing
from phoenix.evals.metrics import FaithfulnessEvaluator, CorrectnessEvaluator
from phoenix.evals import ClassificationEvaluator

load_dotenv()

llm = LLM(provider="google", model="gemini-flash-latest")

# Load the Arize CSV files
all_spans_df = pd.read_csv("arize_all_spans.csv")
parent_spans = pd.read_csv("arize_top_level_spans.csv")
```

`LLM(provider="google", model="gemini-flash-latest")` is the **judge model** from Section 2 — note it's configured once, then reused across every evaluator in this lecture.

**Get the child spans** — recall from Lecture 6 that `parent_spans` holds only the top-level, root span of each trace (no parent). Everything *inside* that trace — the individual reasoning and tool-call steps from Lecture 4's two-turn agent — lives in the child spans:

```python
child_spans = all_spans_df[
    all_spans_df["parent_id"].notna()
].copy()
```

> **Note:** Lecture 6's export script checked for missing `parent_id` values four different ways (`NaN`, empty string, `"None"`, `"nan"`) before treating a span as top-level. This line only checks `.notna()`, which is a simpler filter — worth being aware of if you're combining both scripts, since a `parent_id` stored as the literal string `"None"` would slip through here as if it *were* a child span.

**Find each trace's final research output**, then attach it to the matching top-level span as `context`:

```python
research_context = {}

for trace_id, group in child_spans.groupby("context.trace_id"):
    # Find spans containing LLM output
    llm_spans = group[
        group["attributes.llm.output_messages"].notna()
    ].copy()

    if len(llm_spans) > 0:
        # Sort chronologically, take the final LLM response
        llm_spans = llm_spans.sort_values("start_time")
        final_response = llm_spans.iloc[-1]

        output = final_response.get("attributes.output.value", "")

        if pd.notna(output) and output:
            # Limit context to 5000 characters
            research_context[trace_id] = str(output)[:5000]

# Add research context to parent spans
parent_spans["context"] = (
    parent_spans["context.trace_id"].map(research_context)
)

matched = parent_spans["context"].notna().sum()
print(f"Added context to {matched}/{len(parent_spans)} top-level spans")

output_file = "arize_top_level_spans_with_context.csv"
parent_spans.to_csv(output_file, index=False)
print(f"Final CSV saved as: {output_file}")
```

This is doing something specific: within each trace, there can be multiple LLM calls (recall Lecture 4's two-turn research-then-write pattern). Sorting by `start_time` and taking the *last* LLM span with output is how the code finds the agent's final research findings — the material the written report should actually be grounded in.

---

## 5. Running a Built-In Eval: Correctness

With `context` attached, the first built-in judge to try is **Correctness**:

```python
correctness_eval = CorrectnessEvaluator(llm=llm)

with suppress_tracing():
    correctness_results = evaluate_dataframe(
        dataframe=parent_spans, evaluators=[correctness_eval]
    )

correctness_results.to_csv("correctness_results.csv", index=False)
print("Correctness Evaluation Results saved to correctness_results.csv")
```

`suppress_tracing()` here is the same guardrail from Lecture 6 — the eval run itself shouldn't generate new spans back into Arize AX.

The result: **0 out of 13 passed.** Not one report was graded correct.

---

## 6. Why We're Starting With Faithfulness

A 0/13 pass rate doesn't necessarily mean the agent is producing 13 bad reports — it can also mean the eval is asking the wrong question. **Correctness** typically judges an answer against some notion of a fixed, known-right answer. But this agent researches **real-time financial data** — stock prices, current news, this week's trends — where there often isn't a single static "correct" answer to check against, and the judge model's own knowledge may already be stale relative to what the agent just searched for.

**Faithfulness** asks a different, more appropriate question for this kind of agent: not *"is this the objectively correct answer,"* but **"is this response actually grounded in the source material the agent gathered?"** For a real-time research agent, that's a much more meaningful thing to check — and it's why context (Section 4) had to be built first: faithfulness has nothing to check faithfulness *against* without it.

The broader lesson: **choosing the right eval matters more than tuning the one you already picked.** A perfectly-tuned Correctness eval would still be asking the wrong question here.

---

## 7. How Faithfulness Works

`FaithfulnessEvaluator` specifically needs three columns to be present on each row:

| Column | What it holds |
|---|---|
| `input` | The user's query |
| `output` | The agent's response |
| `context` | The source material to check the response against |

`input` and `output` already exist on `parent_spans` (Lecture 6). `context` is the column built in Section 4 — without it, there's nothing for faithfulness to compare the output against.

---

## 8. Run Faithfulness

Because faithfulness requires `context`, it only runs on the subset of spans that actually have it:

```python
faithfulness_eval = FaithfulnessEvaluator(llm=llm)

# Only run on spans that have context
spans_with_context = parent_spans[parent_spans["context"].notna()].copy()

with suppress_tracing():
    faith_results = evaluate_dataframe(
        dataframe=spans_with_context,
        evaluators=[faithfulness_eval]
    )

faith_results.to_csv("faithfulness_results.csv", index=False)

faith_scores = pd.json_normalize(faith_results["faithfulness_score"])
print("Faithfulness results:")
print(f"  {faith_scores['label'].value_counts().to_dict()}")

print("Correctness gave us 0/13 passes — not useful for real-time data.")
print("Faithfulness gives us a meaningful split — choosing the right eval matters more than tuning it.")
```

Unlike Correctness's uniform 0/13, faithfulness produces a **meaningful split** between passing and failing reports — because it's measuring something the data can actually answer: whether each report stayed grounded in what the agent found, not whether it matches some external ground truth.

---

## 9. Built-Ins Aren't Enough

Faithfulness and Correctness are general-purpose — useful across almost any agent. But some judgments are specific to *your* application. For this financial agent, one question matters that no built-in eval covers: **is this report actually useful to act on, or just a summary of facts?** That requires a **custom rubric**.

---

## 10. Custom Rubrics: The Structure

Arize AX's docs recommend a rubric built from four parts:

1. Define the judge's role
2. Explicit pass/fail criteria
3. Label the data with XML tags
4. Define output choices outside the prompt

This lecture adds a fifth piece on top of AX's four, as a deliberate addition rather than a requirement: **labeled examples**, one for each outcome. The next few sections build the `actionability` rubric piece by piece, in this order.

### Part 1 — Define the Role

```text
You are an expert financial analyst evaluator. Your task is to judge whether
a financial report provides actionable investment guidance, not just raw data.
```

This framing matters beyond politeness — it tells the judge model *what kind of expert* to reason as, which shapes what it treats as relevant.

### Part 2 — Explicit Pass/Fail Criteria

```text
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
```

**Criteria come from error analysis** — this is the direct payoff of Lecture 5's practice of reading real traces and root-causing failures. A rubric like this doesn't come from guessing what "good" might mean in the abstract; it comes from having actually read enough real reports to know what separates a genuinely useful one from a well-written but empty one.

### Bonus — Labeled Examples

Beyond AX's official four parts, this rubric includes one worked example per label, directly in the prompt:

```text
Example — ACTIONABLE:
"Based on NVDA's 122% YoY revenue growth driven by data center demand,
strong forward P/E of 35x relative to sector median of 22x, and expanding
margins, NVDA presents a compelling growth position. Key risk: concentration
in AI training chips (~70% of revenue). Recommendation: accumulate on
pullbacks below $800."

Example — NOT ACTIONABLE:
"NVDA is a major player in the semiconductor industry. The company has seen
significant growth in recent years driven by AI demand. NVDA's stock has
performed well. Investors should consider various factors when making
investment decisions."
```

Notice both examples describe the *same company* and could plausibly come from the *same underlying research* — the only difference is whether it was turned into a recommendation or left as a summary. That's a much sharper signal for the judge model than two examples about different topics would be.

### Part 3 — Label the Data with XML Tags

```text
<user_query>
{input}
</user_query>

<financial_report>
{output}
</financial_report>
```

Wrapping the actual data to be judged in XML tags gives the judge model an unambiguous boundary between "here is the rubric and examples" and "here is the specific thing you're grading" — reducing the chance the model conflates instructions with the content it's supposed to be evaluating.

### Part 4 — Keep Choices Out of the Prompt

The prompt above never says *"answer ACTIONABLE or NOT ACTIONABLE."* The output labels are defined separately, in the evaluator's configuration:

```python
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
"Based on NVDA's 122% YoY revenue growth driven by data center demand,
strong forward P/E of 35x relative to sector median of 22x, and expanding
margins, NVDA presents a compelling growth position. Key risk: concentration
in AI training chips (~70% of revenue). Recommendation: accumulate on
pullbacks below $800."

Example — NOT ACTIONABLE:
"NVDA is a major player in the semiconductor industry. The company has seen
significant growth in recent years driven by AI demand. NVDA's stock has
performed well. Investors should consider various factors when making
investment decisions."

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
```

Keeping `choices` in code instead of prose is what makes this configuration, not just a prompt: the same rubric text could be reused with different label sets, or the scoring could change from binary to a scale, without touching a single word of the prompt itself.

---

## 11. Chain-of-Thought for Judges

An LLM judge that outputs only a bare label (`"actionable"` / `"not actionable"`) is harder to trust and harder to debug than one that explains its reasoning first. Prompting a judge to reason through the criteria before committing to a label — the same "think it through, then answer" pattern used to improve reasoning in other LLM tasks — tends to produce more consistent, more calibratable judgments, which matters given Lecture 2's point that LLM-as-a-judge evaluators are non-deterministic and need calibration in the first place. It also produces something concrete to read afterward, which is exactly what the next section relies on.

---

## 12. Wire It Up

```python
with suppress_tracing():
    action_results_df = evaluate_dataframe(
        dataframe=parent_spans, evaluators=[actionability_evaluator]
    )

action_results_df.to_csv("actionability_results.csv", index=False)
print("Actionability Evaluation Results saved to actionability_results.csv")
```

Note this runs against the **full** `parent_spans`, not `spans_with_context` — unlike faithfulness, judging actionability doesn't require the research context, only the final `input`/`output` pair.

---

## 13. Read the Explanations

Same principle as Lecture 6's `explanation` field on the ticker eval: a label alone ("not actionable") tells you *that* something failed, not *why*. Reading the judge's stated reasoning for each result — not just tallying pass/fail counts — is what turns this eval from a dashboard number into something you can act on, the same way Lecture 5's close reading of raw traces turned into the root-cause categories this rubric's criteria were built from in the first place.

---

## Key Takeaways

1. **LLM judges exist for what code can't check** — meaning, quality, and grounding, not just structure.
2. **Every judge is judge model + rubric + data** — keeping these separate is what makes each one independently improvable.
3. **Built-in evals cover common cases with no prompt engineering** — but the right built-in still has to match what your system actually needs to be judged on.
4. **A uniform failure result (0/13) can mean the eval is wrong, not the system** — Correctness failed everything here because it wasn't the right question to ask of a real-time-data agent.
5. **Faithfulness needs a `context` column that often has to be constructed**, not just an `input`/`output` pair — for this agent, that meant extracting the agent's own research from its child spans.
6. **A strong custom rubric follows a specific structure**: role, criteria, labeled examples, XML-tagged data, and choices defined in code rather than prose.
7. **Rubric criteria should come from error analysis** — the same close reading from Lecture 5, not from guessing what "good" looks like in the abstract.
8. **Reading a judge's explanations, not just its labels, is what makes an LLM-as-a-judge eval actionable** rather than just a score.

---

## Check Your Understanding

Before moving to Lecture 8, you should be able to answer:

1. What are the three components every LLM judge is built from?
2. Why did the Correctness eval fail all 13 reports, and what did that reveal — about the agent, or about the eval?
3. What three columns does `FaithfulnessEvaluator` require, and where did `context` actually come from in this pipeline?
4. Why does a custom rubric wrap the data being judged in XML tags?
5. Why are the `choices` defined in the evaluator config instead of inside the prompt text?
6. Where do good rubric criteria come from, according to this lecture?
7. Why does reading a judge's stated explanation matter as much as reading its label?

---

## Summary

Code evals can check structure; only an LLM judge can check meaning — but that power comes with real design responsibility. Built-in evaluators like Correctness and Faithfulness save you from writing a rubric from scratch, but picking the *right* one for what your system actually does matters more than tuning whichever one you happened to reach for first. When no built-in fits — like judging whether a financial report is genuinely actionable — a well-structured custom rubric, grounded in real error analysis and built from a clear role, explicit criteria, labeled examples, and cleanly separated output choices, is what turns a subjective judgment call into something you can run, trust, and read the reasoning behind at scale.
