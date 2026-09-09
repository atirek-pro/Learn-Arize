# Lecture 10: Datasets and Experiments

> **Learning objective:** Turn failing (and passing) traces into a reusable benchmark, use it to run controlled experiments against agent changes, and know when a fix is actually validated — closing the loop all the way back to Lecture 1's "vibes" problem with real numbers instead of impressions.

---

## 1. The Problem with One-Off Fixes

Fixing a single failing trace feels productive in the moment, but it doesn't tell you much on its own: did the fix generalize to other similar cases, or just that one? Did it accidentally break something that was working before? Without a way to re-check the fix against a stable, repeatable set of cases, every fix is a one-off — you're back to judging by impression, the exact "vibes" problem from Lecture 1, just applied to your own patches instead of the model's output.

---

## 2. Save Failures as a Dataset

The fix: turn the failing traces you already have into something reusable.

1. Filter to failing traces in Arize AX — using the eval labels from Lectures 6–7 (a `fail` on the ticker check, a `not actionable` label, a low faithfulness score) to isolate exactly the cases that need attention.
2. Click **"Save as Dataset."**
3. **Now you have a fixed benchmark** — a stable snapshot of real, known-broken cases you can test any future fix against, instead of re-gathering examples from scratch every time.

---

## 3. Save Passing Traces Too

A dataset of failures alone can only tell you if you're fixing things. It can't tell you if you're breaking things that were already fine. That needs a second dataset:

- **Failures dataset** → tracks recall: are we actually catching (and fixing) the bad cases?
- **Passing dataset** → tracks that good responses stay good after a change.

**Together, these give you TPR and TNR over time** — the true positive rate (are previously-broken cases actually getting fixed) and the true negative rate (are previously-good cases staying good). Watching only one of these is watching half the picture: a prompt change that fixes every failure but quietly regresses 20% of what used to work is not a net win, and you'd only see that by tracking both sets side by side.

---

## 4. Your Datasets Evolve Over Time

Where your test cases come from shifts as the system matures:

| Stage | Primary data source |
|---|---|
| **Pre-production** | Synthetic test cases |
| **Early production** | A mix of synthetic and real traces |
| **Mature** | Mostly real production traces, labeled |

This is the natural continuation of Lecture 5's "where to get test data" guidance — synthetic before you have users, real after. What's new here: **the union of your failure and passing datasets is your golden dataset** (Lecture 9) — not a separate thing you build once, but something that keeps growing as production surfaces new cases in both directions.

---

## 5. Improve the Agent: Let an LLM Do It

Once you know *what's* broken (Lecture 5's root causes, Lecture 7's judge explanations), rewriting the prompt doesn't have to be entirely manual:

- Feed an LLM the current prompts, the relevant judge explanations, and your own requirements for what needs to change.
- The LLM finds the common themes across the failures and proposes rewrites — for this agent, that means both `RESEARCH_PROMPT` and the `instruction` field from Lecture 4.
- This can run as a single API call, reusing whatever LLM-calling setup you already have in place for your evals.

> **Worth double-checking:** your notes describe this as running through "the same package the judge uses," implying the Anthropic SDK directly. The judge code built in Lecture 7 actually called an LLM through Phoenix's `LLM` wrapper (`phoenix.evals.llm.LLM`, configured with `provider="google"`), not the raw Anthropic SDK — so if you're planning to literally reuse "the same package," it's worth confirming which interface your actual eval setup uses before assuming they match. The underlying idea holds either way: reuse whatever LLM-calling infrastructure your evals already have rather than standing up something new just to rewrite a prompt.

---

## 6. Every Change Is Grounded in a Finding

The point of Section 5 isn't "let an LLM edit your prompts freely" — it's that the *input* to that rewrite is a specific, traceable finding: a root-cause category from Lecture 5, a judge explanation from Lecture 7, a disagreement pattern from Lecture 9. A prompt change that can't be traced back to a specific piece of evidence is a guess, not a fix — and guesses are exactly what the rest of this lecture exists to stop you from shipping on faith.

---

## 7. Run an Experiment

With a grounded change in hand and a failures dataset to test it against, run it as a controlled experiment:

```python
experiment, experiment_df = arize_client.experiments.run(
    name="improved-prompts-v1",
    dataset="ax-financial-demo-fails",
    space=SPACE_ID,
    task=improved_agent_task,
    evaluators=[actionability_eval],
)
```

Notice what's being reused here: `dataset="ax-financial-demo-fails"` is exactly the kind of failure dataset built in Section 2, and `evaluators=[actionability_eval]` is the same custom judge built in Lecture 7 — nothing about the eval changes, only the agent version being tested against it.

---

## 8. The Task Abstraction

`task=improved_agent_task` is doing the actual work of defining *what's being tested*: a task is the piece of code that takes one dataset example and runs it through a specific version of your agent to produce an output. Swapping in a new prompt or instruction means writing a new task function, not touching the dataset or the evaluator at all.

That separation is deliberate — it's what keeps the dataset and the grading criteria fixed while only the thing you actually changed (the agent version) varies between runs.

---

## 9. What Experiments Show You

Put together, Sections 7–8 give you a genuine controlled comparison: **same inputs, same evaluators, different agent version. The only variable is your change.**

This is the direct payoff of everything from Lecture 6 onward — a ticker eval, a faithfulness check, or an actionability judge only becomes a meaningful comparison tool once it's run against a fixed dataset with only one thing different between runs. Change the dataset or the evaluator between runs, and you've lost the ability to say the score difference came from your prompt change at all.

---

## 10. Compare the Results — No Vibes, Just Numbers

This is where the course closes its first loop: Lecture 1 opened with the **"vibes" problem** — judging a prompt change by skimming a handful of outputs and deciding it "feels better." An experiment run this way replaces that entirely. Prompt v1 scored X% on the failures dataset; prompt v2 scored Y%, on the *exact same cases*, graded by the *exact same evaluator*. That comparison is deterministic enough to make a real decision from — not a vibe, a number.

---

## 11. The Eval-Iterate Cycle

Sections 1–10 describe one repeatable loop:

```text
Find failures → Read explanations → Fix the prompt → Run experiment → Repeat
```

Each stage maps directly onto earlier lectures: finding failures is Lecture 6–7's evals; reading explanations is Lecture 5 and 7's practice of reading *why*, not just the label; fixing the prompt is Sections 5–6 here; running the experiment is Section 7. The cycle doesn't end — a fixed set of failures becomes the input to the next round, same as production traffic becomes new golden-dataset material in Section 4.

---

## 12. How Many Samples Do You Need?

The size of your dataset changes what kind of conclusion you're entitled to draw from it:

- **12–20 examples** → enough for a **directional signal** — "this looks like it's moving the right way" — but not enough to be confident.
- **200–400 samples** → the range needed to support an actual **shipping decision**.

The reason the jump is so large: **halving the margin of error requires roughly 4x the sample size.** This follows from how statistical uncertainty on a proportion shrinks — margin of error scales with 1 divided by the square root of your sample size, so cutting it in half means quadrupling the denominator underneath the square root. A quick 15-example check after a prompt tweak is a reasonable sanity check; treating that same 15-example result as grounds to ship to everyone is not.

---

## 13. Impact Hierarchy

Not every lever you could pull is equally worth pulling. As a rough rule of thumb, ordered from highest to lowest expected impact:

1. **Data quality fixes** — cleaning up what the system is trained or grounded on tends to move the needle the most.
2. **Prompting improvements** — the fast, cheap lever this lecture spends most of its time on.
3. **Model selection** — swapping the underlying model can help, but it's a bigger, costlier change (recall Lecture 1: this is exactly why you need evals before switching at all).
4. **Hyperparameter tuning** — temperature, top-p, and similar settings — generally the smallest expected payoff of the four.

This isn't a hard law for every system, but it's a useful prioritization default: before reaching for a bigger, more expensive lever further down the list, make sure the cheaper ones above it have actually been tried.

---

## 14. Eval-Driven Development

Taken to its logical endpoint, this lecture's practices suggest a development order, not just a debugging loop: **write the eval before you build the feature.** This is the AI-development version of test-driven development — instead of writing a test that defines correct behavior before writing the code, you write the eval that defines what "good" output looks like before building the prompt or agent behavior meant to produce it.

**The eval defines what "done" means.** A feature isn't finished when it seems to work — it's finished when it passes the eval that was written, deliberately, before a line of the feature existed.

---

## 15. Who Can Write Evals?

If an eval defines "done," then writing one isn't purely an engineering task. **Product managers, customer success, and salespeople** are often better positioned to write a rubric like Lecture 7's actionability criteria than an engineer is — they're the ones who've actually seen what separates a report a customer finds useful from one that just looks polished.

This is the direct payoff of Lecture 5's point that defining success is cross-functional work: the people who know what "good" looks like from the outside are exactly who should be writing the criteria an eval enforces, not just the people implementing the system being judged.

---

## Key Takeaways

1. **A one-off fix without a saved benchmark to test it against is unverifiable** — you can't tell if it generalized or just patched one case.
2. **Save both failing and passing traces as datasets** — tracking only failures hides regressions in what already worked.
3. **Your golden dataset is a moving target**, built from the union of your failure and pass sets as production data accumulates.
4. **A prompt fix should trace back to a specific finding**, not a guess — a root cause, a judge explanation, a disagreement pattern.
5. **Experiments isolate one variable** — same dataset, same evaluators, only the agent version changes — which is what makes the comparison meaningful.
6. **This is what finally replaces "vibes" with numbers** — the exact problem Lecture 1 opened with.
7. **Sample size determines what conclusion you're entitled to draw** — 12–20 examples for direction, 200–400 for a shipping decision, with margin of error shrinking only as the square root of sample size.
8. **Not every improvement lever is equally worth pulling** — data quality and prompting typically beat model swaps and hyperparameter tuning.
9. **Writing the eval before building the feature turns "done" into something measurable**, and that rubric is often best written by the people closest to the user, not just engineers.

---

## Check Your Understanding

Before wrapping up the course, you should be able to answer:

1. Why does a one-off fix to a single failing trace not actually prove anything on its own?
2. Why is a passing-traces dataset necessary in addition to a failures dataset?
3. What makes your golden dataset a "moving target" rather than something built once?
4. What does it mean for a prompt change to be "grounded in a finding," and why does that matter?
5. What does the `task` abstraction in an experiment actually control, and what does it deliberately leave fixed?
6. Why does halving your margin of error require roughly four times the sample size, not double?
7. Why might a product manager or salesperson write a better eval rubric than an engineer, for a given system?

---

## Summary

This lecture closes the loop the whole course opened with: judging AI systems by "vibes" doesn't scale, and everything from Lecture 6 onward — code evals, LLM judges, validated judges — exists to replace impressions with numbers. Saved failure and passing datasets turn one-off fixes into a real, repeatable benchmark; experiments isolate the one variable that actually changed; and sample size, prioritization, and eval-first development all shape how much confidence a given result actually deserves. The endpoint isn't a single clever eval — it's a discipline where every change to an AI system is grounded in a finding, tested against a fixed benchmark, and measured well enough to know, with real numbers, whether it actually helped.
