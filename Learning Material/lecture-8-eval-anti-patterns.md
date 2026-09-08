# Lecture 8: Eval Anti-Patterns

> **Learning objective:** Recognize three common mistakes that quietly undermine an eval program — the "God Evaluator," conflating guardrails with aspirational metrics, and shipping unvalidated evals — and know the practice that avoids each one.

This lecture is less about new code and more about judgment calls that determine whether the evals built in Lectures 6–7 actually hold up over time.

---

## 1. The God Evaluator

It's tempting to build one big eval that scores "is this response good?" — a single number covering accuracy, tone, completeness, safety, and everything else at once. This is the **God Evaluator**, and it's an anti-pattern for a simple reason: **when it fails, you don't know why.**

A single composite score that drops from 0.8 to 0.6 could mean the agent started hallucinating, got more verbose, missed a ticker, or all three at a smaller scale each — you can't tell which from the number alone, and you can't fix what you can't isolate.

**The fix: one evaluator per dimension.** This is exactly the pattern the last two lectures already followed without naming it:

- Lecture 6's ticker-mention eval checks one thing — did the output mention every requested ticker.
- Lecture 7's Faithfulness eval checks one thing — is the output grounded in the research context.
- Lecture 7's custom Actionability eval checks one thing — does the report give usable guidance.

Each one can fail independently, get read independently (Lecture 6 and 7's explanation fields), and get fixed independently. That's the entire point: a failure in one dimension shouldn't be buried inside a blended score alongside four other things that were actually fine.

---

## 2. Guardrails vs. North-Star Metrics

Not every eval should have the same consequence when it fails. Two categories matter here, and confusing them is its own anti-pattern:

| | Guardrails | North-Star Metrics |
|---|---|---|
| **What they are** | Ship-blockers | Aspirational targets |
| **What a failure means** | Do not deploy | Room to improve |
| **Example from this course** | "Every requested ticker must be mentioned" (Lecture 6) | "Reports should be actionable" (Lecture 7) |

A **guardrail** is a line you don't cross — dropping a requested ticker from a financial report is a hard failure, not a matter of degree. A **north-star metric** is something you want to trend upward over time, but a single report scoring "not actionable" isn't, by itself, a reason to halt every deployment.

**Know which is which before you wire anything into CI.** This decision isn't automatic from the eval's mechanics — a code eval isn't automatically a guardrail and an LLM judge isn't automatically a north-star; it depends on what failing that specific check actually means for your system. The test worth asking of any eval: *if this fails on a real deployment, do we block the release, or do we log it and keep iterating?* If the honest answer is "block," treat it as a guardrail. If it's "watch the trend," it's a north-star.

---

## 3. How This Plays Out in Practice

Put together, these two ideas change what "wiring up evals" (Lecture 1's CI quality gate) actually looks like:

- **Guardrails become gates.** A guardrail eval failing on a new prompt or model version is exactly the "reject the change" branch from Lecture 1's CI diagram — automatic, non-negotiable, no human judgment call required in the moment.
- **North-stars become dashboards, not gates.** These get tracked over time, reviewed in aggregate, and used to prioritize what to work on next (Lecture 5's frequency × severity) — but a single failing case shouldn't block a release on its own.

Mixing the two up in either direction causes real damage: treating a north-star as a guardrail stalls shipping over metrics that were never meant to be pass/fail thresholds; treating a guardrail as a north-star lets a genuine, ship-blocking regression quietly through because nothing was actually watching for it in the moment.

---

## 4. Treat Eval Prompts Like Code

An eval — especially an LLM-as-a-judge rubric like Lecture 7's actionability prompt — isn't a one-time artifact you write once and trust forever. It should be developed with the same discipline as the code it's grading:

- **Version them.** A rubric change is a behavior change in your quality bar, exactly the way a prompt change is a behavior change in your agent (Lecture 1). If you can't tell which version of an eval produced a given result, you can't trust a trend line built from it.
- **Test them on examples where you know the answer.** Before trusting an eval's judgment on real, unlabeled traces, run it against a small set of cases you've already hand-labeled — cases you're confident are actionable and cases you're confident aren't. If the eval disagrees with your own confident judgment on the easy cases, it's not ready for the hard ones.
- **Small wording changes shift results.** This isn't a hypothetical risk — it's the direct consequence of Lecture 2's point that LLM-as-a-judge evals are non-deterministic and need calibration. Rewording a single criterion in a rubric can shift which reports pass, the same way it can shift what the agent being graded produces.

The line worth internalizing: **an unvalidated eval is a fancy way of being wrong at scale.** A human spot-checking occasionally is wrong sometimes, inconsistently. An automated eval that's miscalibrated is wrong the *same* way, on *every single trace*, with the confidence of a dashboard number — and because it's automated, nobody's instinct tells them to double-check it.

---

## 5. Don't Ship Evals You Haven't Validated

The practical version of Section 4's "test on known examples": before an eval — built-in or custom — gets wired into a dashboard or a CI gate, check its own accuracy first.

- Build a small labeled set: a handful of cases where you, a human who's actually read the traces (Lecture 5), already know the right answer.
- Run the candidate eval against that set and check whether it agrees with you.
- Only once it does — consistently, not on a lucky handful of cases — treat its judgment on new, unlabeled traces as trustworthy.

Lecture 7's Correctness eval failing 13/13 reports is a good example of why this step matters: a 0% pass rate needs to be diagnosed, not assumed to mean the system is completely broken. In that case, the eval itself was asking the wrong question of a real-time-data agent — a validation step against known-good examples would have surfaced that mismatch before it ever reached a dashboard, rather than after.

---

## 6. Eval Debt Is Real

Technical debt is a familiar idea: code written quickly, under pressure, that works for now but accumulates cost later. **Eval debt** is the same pattern applied to your evals themselves:

- A rubric written once, under deadline pressure, never revisited as the product changed underneath it.
- An eval nobody remembers the reasoning behind — no version history, no record of what examples it was validated against, no owner.
- Guardrails and north-stars that were never explicitly separated (Section 2), so nobody's sure anymore which failures are supposed to block a release.

The danger compounds specifically because evals are the thing decisions get made from — a ship/no-ship call, a "the new model is better" conclusion (Lecture 1), a prioritization decision (Lecture 5). An eval that's quietly gone stale doesn't just produce a wrong number; it produces wrong decisions built on top of that number, and those decisions look just as confident as ones built on a healthy eval. Treating eval maintenance — revalidating, re-versioning, occasionally re-reading the raw traces behind a metric — as ongoing engineering work, not a one-time setup step, is what keeps that debt from accumulating unnoticed.

---

## Key Takeaways

1. **One evaluator per dimension, not one eval that checks everything** — a failure you can't isolate is a failure you can't fix.
2. **Guardrails block releases; north-stars guide improvement** — the same eval mechanics can serve either role, but the decision of which one has to be explicit.
3. **Guardrails belong in CI gates; north-stars belong on dashboards** — mixing them up either stalls shipping or lets real regressions through.
4. **Eval prompts need the same discipline as code** — versioned, tested against known-answer examples, and understood to be sensitive to small wording changes.
5. **An unvalidated eval is confidently wrong at scale** — validate against labeled examples before trusting its judgment on anything new.
6. **A surprising eval result (like a 0% pass rate) should trigger diagnosis of the eval, not just the system** — it might be asking the wrong question.
7. **Eval debt compounds silently** — because decisions get built on eval output, a stale or unvalidated eval produces wrong decisions that look just as confident as right ones.

---

## Check Your Understanding

Before moving to Lecture 9, you should be able to answer:

1. Why is a single composite "quality score" harder to act on than several single-dimension evals?
2. What question can you ask to decide whether a specific eval should be a guardrail or a north-star?
3. What goes wrong if a north-star metric is wired into a CI gate as if it were a guardrail?
4. What does it mean to "treat eval prompts like code," concretely?
5. Why is validating an eval against known-answer examples necessary before trusting it on new data?
6. What should a 0% (or 100%) pass rate on a new eval prompt you to investigate first?
7. What is "eval debt," and why does it compound differently than ordinary technical debt?

---

## Summary

Building evals (Lectures 6–7) is only half the work — keeping them trustworthy is the other half, and that's where most eval programs quietly fail. A single evaluator trying to judge everything hides exactly the information you need to fix anything; conflating a ship-blocking guardrail with an aspirational north-star either stalls releases or lets regressions through unnoticed; and an eval prompt that's never been validated against known-answer examples can be confidently, silently wrong on every trace it grades. None of these mistakes look like failures in the moment — they look like a working eval program, right up until a decision gets made on top of one that wasn't actually measuring what anyone thought it was.
