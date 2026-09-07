# Lecture 2: Traces, Evals, and Why Agents Make This Harder

> **Learning objective:** Understand the difference between traces and evals, the two main types of evals and when to use each, and why agentic systems are significantly harder to evaluate than a single LLM call.

---

## 1. Traces Are Logs, Evals Are Tests

These two concepts are easy to conflate, but they answer different questions:

| | Purpose | Question it answers |
|---|---|---|
| **Trace** | A record of what happened | "What did the system actually do?" |
| **Eval** | A judgment on that behavior | "Was what it did *good*?" |

A trace is the AI equivalent of a log — it captures the full execution path of a request: what was received, what the model did, what tools were called, what came back, and what was finally returned. An eval is the AI equivalent of a test — a check that grades some piece of that behavior as acceptable or not.

You need both. A trace without an eval just tells you what happened, with no judgment on whether it was right. An eval without a trace tells you something failed, but not *where* in the process it went wrong.

---

## 2. Spans: The Building Blocks of a Trace

A trace isn't one big blob of information — it's built from **spans**, where each span represents a single unit of work inside a request: a model call, a tool call, a retrieval step, or a piece of reasoning.

```text
Trace: "What's the weather-adjusted delivery estimate?"
  ├── Span: parse user request
  ├── Span: call weather API
  ├── Span: call inventory/logistics tool
  ├── Span: reasoning step (combine results)
  └── Span: generate final response
```

Because a trace is made of spans, you can evaluate at different levels of granularity — the final answer, an individual tool call, or a single reasoning step. This matters more than it sounds: a wrong final answer might trace back to a fine reasoning step built on a bad tool result. Without span-level visibility, all you'd see is "the answer was wrong," with no way to tell why.

---

## 3. Two Types of Evals

There are two fundamentally different ways to grade an AI output.

### Code Evals
Deterministic checks written as regular code — no model involved in the grading.

- Fast and free to run (no extra API calls)
- Fully deterministic — same input always gives the same result
- Good for anything with a clear, checkable structure

**Examples:** Is the output valid JSON? Does it match a required format? Is it under a length limit? Does it contain (or avoid) a specific string?

### LLM-as-a-Judge Evals
A second LLM reads the output and grades it against a rubric.

- Can judge meaning, not just surface structure
- Flexible — works for open-ended, natural-language outputs
- Non-deterministic — the judge itself needs calibration and testing, the same way you'd test any other model-based component

**Examples:** Is this response accurate given the retrieved context? Is the tone appropriate? Is this answer actually relevant to what was asked?

---

## 4. When to Use Which

| Use **code evals** for | Use **LLM-as-a-judge** for |
|---|---|
| Format and structure | Accuracy |
| Required fields present | Relevance |
| Length/format constraints | Tone |
| Hard constraints (e.g. no PII) | Faithfulness to source material |

Most real systems need **both**. Code evals catch the mechanical failures cheaply and instantly; LLM judges catch the semantic failures that plain code can't detect — like a response that's well-formatted but subtly wrong, off-topic, or unfaithful to the retrieved context.

---

## 5. Why Agents Make This Harder

A single LLM call has one place to go wrong:

```text
Input → Output
```

An agent has many:

```text
Input → Tool Call → Result → Reasoning → Tool Call → Reasoning → Output
```

Every arrow in that chain is a place a failure can be introduced — a wrong tool chosen, a bad argument passed to it, a misread result, a flawed reasoning step built on top of it. And because each step feeds the next, **errors cascade**: a small mistake early in the chain can compound into a completely wrong final answer, even though every individual step looked locally reasonable.

This is exactly why span-level tracing (Section 2) matters for agents specifically — an eval on the final output alone can tell you *that* something went wrong, but not *which* step caused it.

---

## 6. Multi-Agent Complexity

Some systems don't use just one agent — they route work between multiple specialized agents: a **triage** agent decides what a request needs, then hands it off to a **specialist** agent to handle it.

```text
User Request → Triage Agent → hands off to → Specialist Agent → Output
```

Each handoff is an additional layer where things can go wrong on top of everything already possible within a single agent:

- Did triage route to the *right* specialist?
- Did the handoff preserve the necessary context?
- Did the specialist correctly pick up where triage left off?

More agents and more handoffs mean more surface area for failure — evaluation has to account for the routing decisions themselves, not just each agent's individual output.

---

## 7. Cascading Failures Are Worse Than Obvious Ones

Consider this chain: **bad retrieval → bad reasoning → a confidently wrong output.**

The dangerous part isn't the initial mistake — it's that the final response can still read as polished, coherent, and confident. The user has no visual signal that anything went wrong upstream, so they trust it.

This is why a clearly broken response (an error message, a refusal, garbled output) is, in a sense, the *safer* failure. A confidently wrong answer is harder to catch — for the user and for anyone spot-checking outputs — which is exactly why systematic evals matter more than manual review as agents get more complex (see Lecture 1, Section 2 on the "vibes" problem).

---

## 8. Creatively Correct vs. Wrong

Not every eval failure is a real failure. Sometimes an agent finds a valid alternative path to solving the problem — one your eval wasn't written to recognize — and your eval marks it as "fail" even though the agent's answer was actually right.

This is a real limitation to design around, not just an edge case to shrug off:

- Rigid, exact-match evals are the most likely to produce these false negatives.
- LLM-as-a-judge evals can be written to grade the *correctness of the outcome* rather than requiring one specific path to it — but that rubric has to be designed deliberately.
- A failing eval score should prompt a human look before being treated as ground truth, especially early on while you're still calibrating your evals.

---

## 9. Capability Evals and Regression Evals

As a system evolves, you're generally checking for two different things:

- **Capability evals** — *Can it do this new thing?* These test new features or new behavior you're actively trying to add.
- **Regression evals** — *Can it still do the old things?* These re-check existing behavior to make sure nothing broke while you were adding the new capability.

It's easy to only test the new feature you just built and assume everything else still works — but that's exactly the gap regression evals exist to close (this connects directly to Lecture 1, Section 3: evals as the way you catch a regression before a user does).

---

## Key Takeaways

1. **Traces show what happened; evals judge whether it was good.** You need both, and they answer different questions.
2. **Spans give you granularity** — the ability to evaluate a specific step, not just the final output.
3. **Code evals and LLM-as-a-judge evals solve different problems** — structure/format vs. meaning/quality — and most real systems need both.
4. **Every additional step in an agent (and every handoff in a multi-agent system) is a new place for failure to enter**, and errors compound as they move downstream.
5. **A confidently wrong answer is more dangerous than an obviously broken one**, because there's no visible signal to the user that something went wrong.
6. **Not every eval failure is a real failure** — rigid evals can mark a genuinely good, creative answer as wrong.
7. **Capability and regression evals check different things** — adding new functionality and not breaking old functionality are separate concerns, both necessary.

---

## Check Your Understanding

Before moving to Lecture 3, you should be able to answer:

1. What's the difference between a trace and an eval?
2. What is a span, and why does span-level evaluation matter more for agents than for a single LLM call?
3. When would you reach for a code eval instead of an LLM-as-a-judge eval, and vice versa?
4. Why do errors in an agent pipeline cascade instead of staying isolated?
5. What new failure surface does a multi-agent handoff introduce that a single agent doesn't have?
6. Why is a "confidently wrong" output more dangerous than an obvious failure?
7. What's an example of an eval producing a false negative on a "creatively correct" output?
8. What's the difference between a capability eval and a regression eval?

---

## Summary

A single LLM call is relatively easy to reason about: one input, one output, one place for something to go wrong. Agents break that simplicity — every tool call, reasoning step, and handoff is a new opportunity for failure, and those failures cascade downstream into outputs that can look polished while being wrong underneath. Traces give you visibility into that process; evals — both code-based and LLM-as-a-judge — give you a way to judge it. Getting both right, at the right granularity, is what makes it possible to trust an agentic system in production rather than just hoping it holds up.
