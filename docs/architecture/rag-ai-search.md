# Fraud Investigation RAG and AI Search Architecture

## Purpose

Milestone 11 introduces a governed Retrieval-Augmented Generation architecture
for fraud investigation.

The RAG subsystem supplies trusted investigation knowledge to the future
Milestone 12 Fraud Investigation Agent.

## Architecture

```text
Synthetic Fraud Investigation Knowledge
                 |
                 v
Governed Delta Chunk Table
                 |
                 v
Delta Change Data Feed
                 |
                 v
Databricks AI Search
                 |
                 v
Triggered Delta Sync Index
                 |
                 v
Qwen3 Managed Embeddings
                 |
                 v
Hybrid Semantic + Keyword Retrieval
                 |
        +--------+---------+
        |                  |
        v                  v
Retrieval Evaluation    Claude RAG
        |                  |
        v                  v
Hit@1 / Recall@3      MLflow Tracing
MRR / Empty Rate          |
                           v
                   MLflow GenAI Judges
                           |
                           v
                      Quality Gates
                           |
                           v
                   RAG Quality History