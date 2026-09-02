# Milestone 13 — Fraud Agent Evaluation Architecture

## Purpose

Milestone 13 turns the M12 fraud-investigation agent into an evaluated,
regression-gated AI capability.

The evaluation architecture measures both **what the agent says** and
**how it gets there**.

```text
Golden investigation cases
          |
          v
M12 fraud-investigation agent
          |
          +---- MLflow trace
          |
          +---- tool trajectory
          |
          v
Deterministic scorers
          +
Structured LLM judge
          |
          v
Per-case quality result
          |
          v
Aggregate regression gates
          |
          +---- PASS
          |
          +---- FAIL
```

## Governed assets

```text
payments_dev.ai.agent_evaluation_dataset
payments_dev.ai.agent_evaluation_results
payments_dev.ai.agent_evaluation_summary
```

## Golden scenarios

The initial development benchmark contains eight cases:

1. strong fraud-risk evidence;
2. low-risk counterexample;
3. cross-border counterexample;
4. duplicate Kafka delivery semantics;
5. calibrated uncertainty;
6. conflicting model/context evidence;
7. knowledge-required investigation;
8. transaction-scope guard.

The setup notebook selects transaction IDs from the actual governed M12
evidence so the benchmark runs against real synthetic EPIP data rather
than hard-coded model outputs.

## Deterministic evaluation

M13 evaluates:

- required-tool selection;
- tool argument correctness;
- transaction-scope compliance;
- repeated/unnecessary calls;
- response structure;
- source citation correctness;
- human-review requirement;
- autonomous-action safety.

These checks are reproducible and do not require another language model.

## LLM-as-a-judge evaluation

A structured OpenAI judge evaluates:

- groundedness;
- evidence completeness;
- investigation quality;
- risk/counter-indicator balance;
- calibrated uncertainty.

The judge receives only:

```text
golden-case contract
+
captured M12 tool evidence
+
final M12 agent response
```

It does not receive hidden fraud outcomes.

## Critical gates

The following are hard gates:

```text
transaction scope = 100%
safety = 100%
human review = 100%
response structure = 100%
```

Required tools are also enforced per golden case.

Aggregate development gates additionally evaluate:

```text
overall case pass rate >= 85%
tool selection >= 90%
tool arguments >= 95%
tool efficiency >= 85%
groundedness >= 85%
evidence completeness >= 80%
citation correctness >= 90%
```

## Case score

The weighted case score combines deterministic and judge metrics.

A case must:

- reach the minimum overall score;
- use all required tools;
- preserve transaction scope;
- satisfy safety;
- preserve human review;
- satisfy response structure;
- satisfy citation correctness when citations are required.

## Traceability

Every persisted evaluation result retains the M12 `trace_id`.

```text
failed evaluation case
       |
       v
agent_evaluation_results
       |
       | trace_id
       v
MLflow agent trace
       |
       +-- CHAT_MODEL
       +-- TOOL
       +-- RETRIEVER
```

This supports root-cause analysis of prompt, model, tool, and retrieval regressions.

## Runtime architecture

The current development workspace restricts outbound external-model access
from Databricks serverless compute.

Therefore:

```text
Databricks
    |
    +-- golden evaluation dataset
    +-- governed agent evidence
    +-- AI Search
    +-- Delta evaluation history
    +-- MLflow tracking/traces

Local Python
    |
    +-- Claude agent execution
    +-- deterministic scoring
    +-- OpenAI judging
    +-- regression gates
```

The local runner authenticates back to Databricks through `PAYMENTS_DEV`.

## Why M13 is separate from M12

M12 answers:

> Can the governed agent investigate a transaction?

M13 answers:

> Can we measure whether the agent remains correct, grounded, efficient,
> safe, and human-governed when the implementation changes?

This separation creates a production-style AI lifecycle:

```text
Build
  |
  v
Trace
  |
  v
Evaluate
  |
  v
Regression gate
  |
  v
Promote
```
