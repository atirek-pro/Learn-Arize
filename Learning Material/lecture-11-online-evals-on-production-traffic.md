# Lecture 11: Online Evals on Production Traffic

> **Learning objective:** Understand why offline evaluation alone isn't sufficient, configure evals to run continuously against live production traffic, and see how production failures feed directly back into the datasets built in Lecture 10 — closing the loop between shipping and monitoring first raised in Lecture 1.

---

## 1. Why Offline Isn't Enough

Every eval built so far — Lecture 6's code eval, Lecture 7's judges, Lecture 10's experiments — has run **offline**: against a saved dataset, on your own schedule, before or between deployments. That's essential, but it has a hard limit: it can only ever test the cases you already knew to include. Lecture 5 made this point about test data in general, and it applies just as much here — **production will always surface situations your offline dataset never anticipated.** Offline evaluation alone can tell you the system passed its known tests; it can't tell you what's happening to the traffic you haven't looked at yet.

---

## 2. Online Evals

**Online evals** close that gap by running the *same* evaluators you already built in development — automatically, continuously, against real incoming production traces, not a fixed dataset.

A few things carry over directly from earlier lectures with no changes needed:

- The evaluators themselves are unchanged — Lecture 6's ticker check, Lecture 7's faithfulness or actionability judge, all work the same way whether they're run offline or online.
- They can be scoped at different granularities — a **span**, a full **trace**, or an entire **session** — matching the level of granularity Lecture 2 introduced when spans were first defined.

The core shift isn't the evaluator logic; it's *when* and *how often* it runs.

---

## 3. Sample, Don't Grade Everything

Running an LLM judge on every single production trace, all the time, gets expensive fast — and it's usually unnecessary. **A 10% sampling rate is a good default**: it's cheap enough to run continuously, and statistically representative enough to catch real shifts in quality without grading every trace individually.

Arize AX handles the actual sampling mechanics for you — you set a rate, not a manual selection process.

---

## 4. How Online Evals Connect

Online evals aren't a separate system bolted onto everything from Lectures 6–10 — they're the same pipeline, running on a schedule instead of on demand:

- Results get written back onto live spans the same way Lecture 6's `log_eval_to_ax` wrote offline eval results onto saved spans.
- A trace that an online eval flags as a failure is now a candidate for Lecture 10's failure dataset — production monitoring feeding directly into the same golden-dataset pipeline, without a manual export step in between.
- Because it's the same evaluator as offline, a score drop in production is directly comparable to the baseline you already established in Lecture 10's experiments — no need to guess whether a change in the number reflects a real shift or just a different measurement.

---

## 5. Configure an Online Eval

Setting one up means specifying a handful of fields:

| Setting | Example value | What it controls |
|---|---|---|
| **Project** | `ax-financial-demo` | Which traced application this eval runs against |
| **Evaluator** | `actionability` | Which rubric or check to apply (Lecture 7's custom judge, in this case) |
| **Scope** | `trace` | Whether it grades a span, a full trace, or a session |
| **Sample rate** | `10%` | What fraction of matching traffic actually gets evaluated |
| **Run frequency** | `continuous` | How often the eval runs — here, on an ongoing basis rather than a one-time batch |

Once configured, this runs in the background against live traffic without any further manual triggering — the automated counterpart to the notebook-driven runs from Lecture 6–7.

---

## 6. Alyx Eval Builder

Writing a rubric from scratch (Lecture 7's four-part structure) is real work. Arize AX's built-in assistant, **Alyx**, can shortcut the first draft of that process directly from the Eval Builder:

- Describe what you want measured in plain English.
- Alyx generates a rubric template from that description — including the prompt structure and the output labels.
- **You review and tweak it before shipping** — Alyx's draft is a starting point, not a finished, validated rubric. Lecture 9's whole point still applies here: a generated rubric still needs to be checked against a golden dataset before you trust its judgments in production, the same as one you wrote by hand.

---

## 7. Today's Failure Is Tomorrow's Regression

Once an online eval catches a real production failure, that trace shouldn't just get fixed and forgotten. **Add it to your dev datasets.** The moment it's in there, it stops being just "a bug that happened once" and becomes a **regression test** — something every future prompt or model change gets checked against automatically, exactly as described in Lecture 10's Section 3 (failing traces → dataset → fixed benchmark).

This is the mechanism that makes the whole system self-reinforcing: production doesn't just get monitored, it actively makes your offline eval suite better over time.

---

## 8. A Differentiated Dataset

A dataset built this way — real production failures, from your actual users, on your actual system — isn't something you can download or buy. It's built entirely from what genuinely goes wrong in *your* application, which makes it uniquely valuable: no generic benchmark or synthetic test set can substitute for a collection of real cases your own system has actually struggled with. Over time, this differentiated dataset becomes one of the more durable assets an eval program produces — it keeps compounding as long as online evals keep running.

---

## 9. The Model Upgrade Advantage

This closes a loop all the way back to **Lecture 1**: new models ship constantly, and switching to one without evals means weeks of manual testing to have any confidence in the change. Online evals sharpen that advantage further — a team with continuous evaluation running against live traffic doesn't just have a dev-time eval suite to check a new model against; they have a constantly-refreshed, differentiated dataset of real failures (Section 8) and a live signal for how a new model actually performs on real traffic, not just a static benchmark. **Teams without online evals face weeks of testing. Teams with them know in hours** — and the gap between those two outcomes is essentially everything this course has been building toward.

---

## Key Takeaways

1. **Offline evals can only test what you already thought to include** — production will always find cases beyond that.
2. **Online evals reuse the same evaluators from development**, just run continuously against live traffic instead of a fixed dataset.
3. **Sampling (10% is a solid default) keeps online evaluation affordable** without sacrificing a statistically meaningful signal.
4. **Online eval results feed directly into the same pipeline as offline evals** — a flagged production trace can become tomorrow's regression test.
5. **Alyx can draft a rubric from plain English**, but a generated rubric still needs review and validation (Lecture 9) before it's trusted in production.
6. **Real production failures form a differentiated dataset** that no synthetic or off-the-shelf benchmark can replicate.
7. **This is what turns "weeks of manual testing" into "hours of confident evaluation"** when a new model ships — the practical payoff of everything from Lecture 1 onward.

---

## Check Your Understanding

1. Why can't offline evaluation alone ever be fully sufficient, no matter how good the dataset is?
2. What stays the same, and what changes, when an evaluator moves from offline to online use?
3. Why is 10% sampling usually a reasonable default rather than grading every trace?
4. How does a production failure caught by an online eval end up becoming a regression test?
5. Why does an Alyx-generated rubric still need the validation process from Lecture 9?
6. What makes a dataset built from real production failures "differentiated" in a way a purchased or synthetic benchmark isn't?
7. Why does having online evals in place specifically shorten the time it takes to evaluate a new model release?

---

## Summary

Every eval built earlier in this course was strong evidence about the cases you already knew to test — online evals extend that same evidence to the traffic you didn't anticipate, running continuously and automatically against real production traces at a sampled, affordable rate. The real power isn't just catching failures faster; it's that those failures flow straight back into the dev datasets from Lecture 10, turning today's production incident into tomorrow's permanent regression test. That compounding cycle — production feeding evaluation, evaluation feeding the dataset, the dataset protecting every future change — is what finally delivers on Lecture 1's opening promise: knowing, within hours instead of weeks, whether a change actually made things better.
