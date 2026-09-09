# Lecture 9: Can You Trust Your Judge?

> **Learning objective:** Treat an LLM judge as a classifier whose accuracy has to be measured, not assumed — build a golden dataset to check it against, use precision and recall to know what kind of mistakes it's making, recognize common judge biases, and know when a suspiciously bad score means the eval is broken, not the system.

Lecture 7 built LLM judges. This lecture asks the question that has to come next: **how do you know the judge itself is any good?**

---

## 1. Your Judge Is a Classifier

Strip away the prompt engineering from Lecture 7, and an LLM judge is doing something very ordinary: it takes an input and makes a **prediction** — pass or fail, actionable or not actionable. A prediction is only as good as its accuracy against **ground truth**, and that means it can be measured exactly the way any classifier is measured.

**Your job isn't just to build the judge — it's to check the judge's homework.** A judge that hasn't been checked against ground truth is exactly the "unvalidated eval" anti-pattern from Lecture 8, just described from a different angle.

---

## 2. Human Judgment Is a Lot of Work

Checking a judge's homework means having an answer key — real human judgments to compare its predictions against. This is genuinely labor-intensive: someone has to read real cases (Lecture 5's practice) and label each one correctly, by hand, before any comparison is possible. There's no shortcut around this step — an eval program's trustworthiness is only as strong as the human labeling effort underneath it.

---

## 3. Building Annotations in AX

Arize AX supports attaching a human judgment — an **annotation** — directly onto a span, trace, or dataset example, so that label lives right alongside the data it describes.

**Through the UI:**

1. Open **Annotation Configs** in the left navigation and click **New Annotation Config**. Define the schema for your label — categorical (e.g. a `Correctness` config with `correct` / `incorrect` values), a numeric score, or freeform text.
2. Open the **Spans** view and find the traces you want to review — optionally filter by span kind, time range, or status to focus your review.
3. On a given span, click the **annotate** button, select your config, and apply the label.

Once an annotation config exists, the same schema can be reused across traces, spans, sessions, and dataset examples, so your `Correctness` or `Actionability` label stays consistent no matter where it's applied.

**By code**, the same idea follows the exact pattern Lecture 6's `log_eval_to_ax` already used for machine-generated eval results: a DataFrame keyed by `context.span_id`, with columns following the `annotation.<name>.label` / `annotation.<name>.score` naming pattern, uploaded via the SDK's `update_annotations` (or the newer `spans.annotate` method). That's the mechanism that turns a human's read-through of real traces into structured data you can compare a judge against.

> **Note:** annotations can only be applied to spans from within roughly the last month — if you're planning to build a golden dataset from older traces, export and label them before that window closes.

---

## 4. Building Your Golden Dataset

A **golden dataset** is your answer key: a set of cases with known-correct labels, built specifically to validate evals against. Building one well takes real care:

- **Write unambiguous tasks.** If a case is genuinely debatable even to a careful human reviewer, it's a bad addition to a golden dataset — you need cases where the right answer isn't in question, so that any disagreement you see later is coming from the judge, not from the task itself.
- **If a task gets a 0% pass rate consistently, suspect the task, not the agent.** This is Lecture 7 and 8's Correctness-eval lesson again: a uniform failure is a signal to check whether you've written a fair, well-posed task before concluding the system is broken.
- **Each task needs a reference solution.** Without one, there's nothing concrete to compare the judge's verdict against — "unambiguous" and "has a reference solution" are really the same requirement stated two ways.
- **Test when behavior *should* occur, and when it *shouldn't*.** A golden set that's all positive examples (cases that should pass) can't tell you whether the judge over-flags — you need negative cases (things that should genuinely fail) too, so the judge is tested on both sides of the line.

---

## 5. Dev/Test Splits for Your Labels

Once you have a labeled golden set, split it in two — a **dev set** you use while actively refining the rubric (Section 9), and a **held-out test set** you don't touch until you think the rubric is done.

The reason for the split: if you tune a rubric against the same examples you're using to measure it, you'll naturally end up with a rubric that fits those specific examples well — without knowing whether it generalizes to cases it hasn't seen. The held-out test set is what tells you whether the rubric actually improved, or just got better at matching the examples you were staring at while writing it.

---

## 6. Compare Judge to Human Labels

With a golden dataset in hand, run the judge on it and line its predictions up against the human labels. Each case falls into one of four outcomes — the judge agreed the case passed, agreed it failed, or disagreed in one direction or the other. That comparison is the raw material for Section 7.

---

## 7. Precision and Recall

Two numbers describe *what kind* of mistakes a judge is making, not just how many:

- **Precision** — when the judge says "fail," is it right? (Of everything the judge flagged as a failure, how many were actually failures?)
- **Recall** — of all the real failures in your golden set, how many did the judge actually catch?

These pull in different directions. A judge that flags almost everything as a failure has high recall (it rarely misses a real one) but low precision (most of its alarms are false). A judge that only flags the most obvious failures has high precision but low recall (it lets subtler real failures through).

---

## 8. Prioritize Recall

For most quality-control uses of a judge, **recall matters more than precision.** A false positive — the judge flags something as a failure that a human then reviews and clears — costs a few minutes of review. A false negative — a real failure the judge waves through — ships straight to users undetected. **It's better to flag too much and let a human dismiss the noise than to miss a real failure entirely.**

This mirrors Lecture 8's guardrail logic directly: a guardrail eval's whole job is to catch every real ship-blocker, even at the cost of occasionally crying wolf.

---

## 9. Fixing the Rubric

When the judge and your human labels disagree, that disagreement is information, not just an error rate to shrug at:

1. **Read the explanations on disagreements.** The judge's stated reasoning (Lecture 7, Section 13) usually shows exactly where its interpretation diverged from yours.
2. **Find the ambiguity.** Often a disagreement traces back to a criterion in the rubric that was vaguer than you realized while writing it.
3. **Tighten the criteria.** Rewrite the ambiguous part specifically, using the disagreement case itself as a concrete example of what needed to be clarified.

**Rubric iteration** is this loop repeated: tighten, re-run against the dev set, check if agreement improved, repeat — always checked against fresh data on the held-out test set (Section 5) before you trust the result.

---

## 10. Judge Pitfalls

LLM judges fail in a few well-documented, predictable ways:

- **Position bias** — the judge favors whichever option appears first (or last), independent of actual quality.
- **Length bias** — longer responses tend to score higher, even when they're not actually better.
- **Confidence bias** — a confidently worded wrong answer fools the judge more easily than a hedged one, echoing the "confidently wrong" problem from Lecture 2 and 5, now applied to the judge itself rather than the agent.
- **Self-preference** — a judge model rates outputs from its own model family more favorably than equivalent outputs from a different model.

---

## 11. Mitigating Self-Preference Bias

The most direct mitigation: **use a different model as the judge than the one being evaluated.** If the agent being graded runs on one model family, choosing a judge from a different family removes the most obvious channel for self-preference to creep in. Where that's not possible, treating self-preference as a known, standing risk — and weighting it into how much you trust a suspiciously favorable judge score — is the fallback.

---

## 12. Detecting Judge Bias

Each pitfall in Section 10 has a matching test:

- **For position bias:** run the same comparison with the option order swapped, and check whether the verdict flips. If it does, the judge is responding to position, not content.
- **For length bias:** hold the actual content quality constant while varying response length, and check whether the score moves anyway.
- **For confidence bias:** deliberately include a confidently-worded but wrong answer in your golden set (Section 4's "test when behavior shouldn't occur" case), and check whether the judge is fooled by tone rather than substance.

These are just Section 4's golden-dataset discipline aimed specifically at the judge's known failure modes, rather than at general accuracy.

---

## 13. The Benchmark Is Human Performance

It's tempting to hold a judge to a standard of "perfect agreement with humans." That standard doesn't actually exist — **humans don't agree with each other perfectly either.** Human inter-rater reliability on genuinely subjective tasks is often only around **0.2–0.3 Cohen's Kappa** — a statistic that adjusts raw agreement for the agreement you'd expect by chance alone. On the standard interpretation scale, that range counts as only "slight" to "fair" agreement, not "the humans were basically unanimous."

That reframes what "good enough" means for a judge: **if your judge is more internally consistent than your human raters are with each other, that's a genuine win**, not a red flag — it means the judge may actually be a more *reliable* (if not necessarily more *correct*) source of repeatable labels than asking a rotating set of humans to do it fresh every time.

---

## 14. Failures Should Seem Fair

A good eval — code, built-in, or custom — should leave you able to answer a simple question when it fails a case: **is it clear what the agent actually got wrong?** If a human reading the failure and the judge's stated reasoning nods along, the eval is doing its job. If a score is failing and nobody reading the explanation can tell what's actually wrong, **the eval itself may be at fault, not the system it's grading** — the same diagnostic instinct from Lecture 7 and 8, now framed as an ongoing habit: if scores stop climbing even as you fix real issues, check the eval before concluding you've hit a wall.

---

## 15. The CORE-Bench Story

This lesson has a well-documented real example. **CORE-Bench** is a benchmark that tests AI agents on scientific reproducibility — setting up a paper's repository, running its code, and correctly answering questions about its results. When Claude Opus 4.5 was first evaluated on it using a standard agent scaffold, it scored just **42%**.

Investigating that low score revealed two separate issues, not one deep flaw in the model. First, switching the agent scaffold itself (from the generic harness to Claude Code) nearly doubled the score to **78%** on its own. Second, a manual review of the remaining failures found real problems in the benchmark's own automated grading — edge cases scored incorrectly and some underspecified tasks — along with at least one task whose reference data had gone stale. Correcting those grading issues brought the final score up to **95%**.

The takeaway holds regardless of the exact numbers: a startlingly low score is a prompt to **investigate the evaluation pipeline itself** — the scaffold, the grading logic, the task specification — not just conclude the system being tested is bad. The specific illustration of "the eval expected 92.1234 but got 92.12" is a simplified, hypothetical version of this idea rather than the literal bug in CORE-Bench — the real story is the scaffold-and-grading combination above, but the underlying lesson (an overly strict or broken grader can make a genuinely capable system look like it's failing) is exactly the same either way.

*Source: [CORE-Bench is solved (using Opus 4.5 with Claude Code)](https://x.com/sayashk/status/1996334941832089732)*

---

## 16. Verify Your Evals

Every idea in this lecture — golden datasets, precision and recall, bias detection, the human-performance benchmark — serves one purpose: **treat your evals with the same skepticism you'd apply to the system they're grading.** The CORE-Bench story is the sharpest version of the lesson: a 42% score looked like a capability problem and turned out to be, in significant part, a measurement problem. An eval you haven't verified can hide a working system behind a broken grader just as easily as it can hide a broken system behind a lenient one — which is exactly why "does the judge deserve to be trusted" has to be an explicit, ongoing question, not an assumption you make once and move on from.

---

## Key Takeaways

1. **An LLM judge is a classifier** — its accuracy is measurable against ground truth, not something to assume.
2. **A golden dataset is unavoidable groundwork** — unambiguous tasks, reference solutions, and both positive and negative cases, built from real human review.
3. **Dev/test splits prevent a rubric from overfitting to the examples used to tune it.**
4. **Precision and recall describe different failure modes** — and for most quality gates, recall (catching real failures) should be prioritized over precision (avoiding false alarms).
5. **Rubric iteration is a loop**: read disagreements, find the ambiguity, tighten the criteria, re-test on held-out data.
6. **Judges have known, testable biases** — position, length, confidence, and self-preference — each with a specific way to detect and mitigate it.
7. **Perfect human agreement isn't the bar** — human inter-rater reliability is often low, so a consistent judge can beat inconsistent humans without being flawless.
8. **A suspiciously bad or inexplicable score is a reason to investigate the eval itself**, not just assume the system failed — exactly what CORE-Bench's 42%-to-95% story shows in practice.

---

## Check Your Understanding

Before moving to Lecture 10, you should be able to answer:

1. Why is "check the judge's homework" a more accurate framing than "trust the judge" once it's built?
2. Why does a golden dataset need negative cases, not just positive ones?
3. Why is a dev/test split necessary even when you already have a labeled golden dataset?
4. In a quality-gate context, why is recall usually prioritized over precision?
5. Name a judge bias and the specific test that would detect it.
6. Why is "the judge disagreed with human raters" not automatically evidence the judge is wrong?
7. What actually caused CORE-Bench's 42% → 95% jump, and why does that matter more than the exact numbers?

---

## Summary

Building a judge (Lecture 7) is not the same as trusting one — that trust has to be earned through the same rigor you'd apply to any classifier: a real golden dataset, a genuine dev/test split, precision and recall tracked separately, and deliberate tests for known biases like position, length, confidence, and self-preference. The bar isn't perfect agreement with humans, since humans themselves often don't agree with each other consistently — it's whether the judge is reliable, its failures are explicable, and its scores can be trusted enough to make real decisions from. The CORE-Bench story is the clearest possible reminder of what's at stake in skipping this step: a model that looked mediocre at 42% turned out to be excellent once the *evaluation*, not the model, got fixed.
