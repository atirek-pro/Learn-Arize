# AI Agent Evaluation with Arize AX

A hands-on learning repository for understanding **AI Agent Evaluation and Monitoring using Arize AX**.

The repository uses a small **Google ADK financial analysis agent** as the experimental system. The goal is to learn how to observe agent behavior, define measurable quality criteria, evaluate traces, validate evaluators, and build a feedback loop for improving agents.

## Learning Objective

Learn the core evaluation workflow for AI agents:

```text
Agent
  ↓
Tracing / Observability
  ↓
Trace Analysis
  ↓
Code Evals + LLM Judges
  ↓
Judge Validation
  ↓
Experiments / Regression Testing
  ↓
Online Evals
  ↓
Monitors & Alerts
  ↓
Failure Analysis
  ↓
Agent Improvements
```

The central idea is to replace **"the agent looks good"** with measurable evidence.

## Repository Structure

```text
learn-arize/
│
├── Evaluation Implementation/
│   ├── custom_eval_in_arize.py
│   ├── evaluate.py
│   ├── LLM-as-a-Judge-Evaluation.py
│   └── run_tests.py
│
├── FinancialAnalysisAgent/
│   ├── __init__.py
│   └── agent.py
│
└── Learning Material/
    ├── lecture-1-why-agents-break-in-production.md
    ├── lecture-2-traces-evals-and-why-agents-make-this-harder.md
    ├── lecture-3-set-up-tracing-with-arize-ax.md
    ├── lecture-4-build-a-traced-financial-agent.md
    ├── lecture-5-read-your-data-before-you-write-evals.md
    ├── lecture-6-code-evals.md
    ├── lecture-7-llm-judges-built-in-and-custom.md
    ├── lecture-8-eval-anti-patterns.md
    ├── lecture-9-can-you-trust-your-judge.md
    ├── lecture-10-how-to-turn-failing-traces-into-a-better-Agent.md
    ├── lecture-11-online-evals-on-production-traffic.md
    ├── lecture-12-monitors-and-alerts.md
    └── lecture-13-from-explanations-to-fixes.md
```

## Learning Path

### 1. Foundations — Lectures 1–2

Understand:

- Why traditional software tests are insufficient for AI systems
- Why agents introduce additional failure points
- Traces, spans, sessions, and agent execution
- Offline vs. online evaluation
- Why evaluation is an engineering discipline rather than manual output inspection

### 2. Observability — Lectures 3–4

Set up Arize AX tracing for the financial agent.

The agent uses:

- **Google ADK**
- **OpenInference**
- **Arize AX**
- **Yahoo Finance via `yfinance`**

Tracing captures model and tool execution as spans, making the agent's behavior inspectable rather than treating the final response as the only observable artifact.

Run:

```bash
python Evaluation\ Implementation/run_tests.py
```

Then inspect the generated traces in your Arize AX project.

### 3. Understand the Data — Lecture 5

Before writing evaluators, inspect the traces.

Learn to identify:

- Inputs and outputs
- Parent and child spans
- Tool calls
- Retrieved context
- Failure patterns
- The actual dimensions of quality that matter for the agent

**Principle:** understand agent behavior first; define the eval second.

### 4. Code Evaluation — Lecture 6

Start with deterministic, structural evaluators.

Example:

```text
mentions_requested_tickers
```

This evaluator checks whether every ticker requested by the user appears in the generated report.

Use code evals when a quality requirement can be expressed deterministically.

### 5. LLM-as-a-Judge — Lecture 7

Use LLM judges when evaluation depends on **meaning rather than structure**.

This repository demonstrates:

- Correctness
- Faithfulness
- Custom Actionability evaluation

An LLM judge consists of:

```text
Judge Model
     +
Rubric
     +
Evaluation Data
```

Built-in evaluators can be used for common evaluation dimensions, while custom rubrics handle domain-specific requirements.

Run:

```bash
python Evaluation\ Implementation/LLM-as-a-Judge-Evaluation.py
```

### 6. Eval Design & Validation — Lectures 8–9

Learn how to build evaluation systems that can actually be trusted.

Key concepts:

- Avoid the **God Evaluator**
- Prefer one evaluator per quality dimension
- Separate **guardrails** from **north-star metrics**
- Validate LLM judges against human-labeled ground truth
- Measure judge precision and recall
- Inspect judge explanations, not only labels

The evaluator itself must be treated as a system that requires validation.

### 7. Experiments & Regression Testing — Lecture 10

Turn real failures into reusable datasets.

```text
Failing Traces
      ↓
Dataset
      ↓
Agent Change
      ↓
Experiment
      ↓
Same Evaluators
      ↓
Compare Results
```

The important experimental rule is:

```text
Same Dataset
Same Evaluators
Different Agent Version
```

This isolates the agent change and makes the comparison meaningful.

### 8. Production Evaluation — Lectures 11–12

Move from offline evaluation to continuous production evaluation.

Learn:

- Online evals
- Sampling
- Production trace evaluation
- Eval-based monitors
- Thresholds
- Alerts
- Regression detection

The transition is:

```text
Offline:
Dataset → Evaluator → Result

Online:
Production Trace → Evaluator → Result → Monitor → Alert
```

Production failures can then become new regression cases for the offline evaluation dataset.

### 9. Closing the Loop — Lecture 13

Use evaluation results to drive agent improvements.

```text
Production Failures
        ↓
Eval Explanations
        ↓
Identify Patterns
        ↓
Coding Agent / Developer
        ↓
Prompt / Tool / Retrieval Fix
        ↓
Experiment
        ↓
Deploy
```

Do not optimize for individual failures. Look for **repeated patterns across explanations**, then verify proposed fixes with experiments before shipping them.

## Evaluation Implementations

| File                           | Purpose                                               |
| ------------------------------ | ----------------------------------------------------- |
| `run_tests.py`                 | Generate agent executions and traces                  |
| `evaluate.py`                  | Implement deterministic code evaluation               |
| `LLM-as-a-Judge-Evaluation.py` | Run built-in and custom LLM judges                    |
| `custom_eval_in_arize.py`      | Run an existing Arize evaluator through an experiment |

The implementations intentionally progress from:

**deterministic checks → semantic LLM evaluation → evaluator validation → experiments**

## Core Concepts

By the end of the repository, you should understand:

- **Trace** — complete execution of an agent request
- **Span** — individual operation within a trace
- **Eval** — measurable test of agent behavior
- **Code Eval** — deterministic evaluation implemented with code
- **LLM Judge** — semantic evaluation performed by another LLM
- **Rubric** — criteria defining what the judge considers correct
- **Annotation** — human-labeled ground truth
- **Dataset** — reusable evaluation examples
- **Experiment** — controlled comparison between agent versions
- **Online Eval** — continuous evaluation against production traffic
- **Monitor** — continuous observation of evaluation or operational metrics
- **Golden Dataset** — curated set of representative passing and failing cases

## Recommended Workflow

Do not start by writing complex evaluators.

Follow this order:

```text
1. Run the agent
2. Inspect traces
3. Understand failure modes
4. Define one evaluation dimension
5. Implement a code eval where possible
6. Use an LLM judge where semantics are required
7. Validate the judge
8. Save failures as datasets
9. Run controlled experiments
10. Move validated evals online
11. Add monitors
12. Feed production failures back into the dataset
```

Start with **one evaluation dimension**, validate it, and expand gradually.

## Setup

Create a Python environment and install the dependencies required by the agent and evaluation scripts.

Configure the Arize AX credentials:

```env
ARIZE_AX_API_KEY=<your-arize-api-key>
ARIZE_AX_SPACE_ID=<your-arize-space-id>

GOOGLE_API_KEY=<your-google-adk-api-key>
```

The agent registers an Arize AX trace provider and instruments Google ADK using OpenInference.

## Goal

This repository is not primarily about learning individual Arize AX API calls.

It is about learning the **engineering methodology behind reliable AI agents**:

> **Observe → Measure → Validate → Experiment → Monitor → Improve**

Evals are treated as ongoing infrastructure rather than a one-time testing step, with production behavior feeding back into development and regression testing.
