# Copilot Standardized Agent Instructions  
**Project:** BMF AI RAG Platform – 5-MVP Roadmap Transformation

---

## Purpose

This document provides **step-by-step, standardized guidance** for GitHub Copilot Pro Agent to research, plan, implement, and validate the BMF AI RAG Platform's incremental MVP roadmap, converting it to a production-grade, enterprise-ready, agentic RAG system.

---

## General Principles

1. **Iterative MVP Delivery**: Implement features in priority order across 5 MVPs, delivering actionable progress at each stage.
2. **Deep Research Before Coding**: For each feature, survey OSS/commercial precedents and best practices; prefer proven patterns.
3. **Explicit Validation**: After each implementation step, run tests, assert metrics, and document validation status.
4. **Documentation-Driven**: Keep detailed comments, docstrings, and update project docs and config schemas with every substantive change.
5. **Compliance & Observability**: Embed compliance, monitoring, and audit features at every layer; document evidence.

---

## Standard Operating Procedure for Each MVP

### For Each Feature:
#### 1. DEEP RESEARCH
- Survey latest code, APIs, methods in OSS leader (LangChain, LlamaIndex, Haystack, AgentSet, Weaviate, Qdrant, Unstructured.io, RAGAS, Langfuse, etc.)
- Summarize at least 1–2 implementation patterns with citations.

#### 2. PLANNING
- Break feature into clear sub-tasks.
- Specify input/output schema, config changes, and dependencies.
- Write test strategy including success metrics.

#### 3. IMPLEMENTATION (STEP-BY-STEP)
- Scaffold all required files/folders and signatures.
- Implement in atomic commits.
- Use test-driven or doc-driven approach where possible.
- Add or update Airflow DAG steps and configs.

#### 4. VALIDATION
- Run/expand corresponding unit/integration/regression tests.
- Collect metrics (latency, retrieval accuracy, chunk counts, quality metrics) and compare to target KPI.
- Run end-to-end flows using `python manage.py pipeline` and/or targeted individual agent runs.
- Document results in a comment block in the relevant code or markdown.

#### 5. DOCUMENTATION
- Update configs, schemas, and onboarding docs.
- Summarize key changes, validation results, and next steps in a `CHANGELOG.md` entry.

---

## MVP-Specific Guidance

### MVP 1: Foundation & Core RAG

- **AgentSet Vector DB Integration**: Research AgentSet SDK patterns, implement ingestion/retrieval client, batch upload, hybrid search, metadata mapping, SHA-256 deduplication.  
  - **Validation:** Test ingestion throughput (>100 chunks/sec), search latency (<200ms P95), and context_precision >80% (RAGAS score).

- **Element-Based Chunking**: Research Unstructured.io/Firecrawl table-extraction; implement element-aware chunker; preserve tables, headings; add tests covering PDF/HTML.
  - **Validation:** All tables are preserved, chunk sizes <1200 tokens, >80% have context overlap.

- **Complete Parser Agent**: Integrate Unstructured.io for parsing; support >15 formats; add coverage tests.
  - **Validation:** Compare parsing output with reference documents.

- **Hybrid Search**: Investigate Weaviate/Qdrant hybrid search; enable BM25+vector fallback; test with retrieval precision/recall benchmarks.

- **Complete Validator Agent**: Build with Great Expectations; run automated expectations post-chunking.
  - **Validation:** Automated pipeline blocks on failed data quality rules.

### MVP 2: Agentic RAG & Intelligence

- **Self-Reflection, Multi-Step Reasoning, Tool Use, Planning**: Deep-dive LangChain LangGraph, LlamaIndex agentic flows; implement autonomous query plan/execution/decomposition; implement tool invocation (for calculators/data APIs).
  - **Validation:** Regression prompts require agentic decomposition; score against expert ground truth.

- **Multi-LLM Support, Multi-Modal**: Add support/config for multiple LLMs and image/structured data, fallback logic.
  - **Validation:** Queries routed by cost/latency/complexity; maintain quality thresholds.

### MVP 3: Evaluation & Quality Assurance

- **RAGAS, DeepEval Integration**: Implement and schedule RAGAS and DeepEval runs on prompt bank; track quality in CI/CD.
  - **Validation:** Block deployment on <85% faithfulness, <90% citation verification.

- **Citation Verification, Hallucination Detection**: For each generated answer, cross-check citations; add fail-safe refuse mode for low-confidence outputs.
  - **Validation:** Regression suite for hallucination/citation coverage.

### MVP 4: Observability & Production

- **Langfuse, Cost/Latency, Alerting**: Add tracing to all agent executions; metrics for tokens/costs/errors/latency; publish Grafana/Streamlit dashboards.
  - **Validation:** Metrics populate dashboards; alerts fire on breach.

- **CI/CD Integration, Docker Compose**: Implement PR-based tests for all features; provide `docker-compose.yaml` for full local stack.
  - **Validation:** All pipeline tests green; `docker-compose up` works end-to-end.

### MVP 5: Enterprise

- **RBAC, Multi-Tenancy, Scaling, Audit Trail**: Research best OSS access control patterns (eg, FastAPI, Django, Weaviate), implement tenant/role system, K8s scale, and full audit log.
  - **Validation:** Coverage tests for user isolation, scaling, and log completeness.

---

## Validation & Progress Reporting

- After each feature, create a progress report in GitHub Discussions or next `CHANGELOG.md` version.
- For blockers or research-limited areas:
  - Summarize current limitations.
  - Propose research or alternative approaches and link to upstream issues/PRs.

---

## Citation & Reference Policy

- Use comment blocks to cite OSS/commercial code, research, and docs sources for each implemented pattern.
- Every non-trivial core pattern and config should have a traceable research justification.

---

## Key References

Refer to `/tmp/bmf_platform_comparison.csv` and `/tmp/bmf_implementation_blueprints.txt` for detailed cross-platform analyses and implementation sketches.

---

## Example Epic/Feature Planning Template

### Feature: [Title]

- **MVP Phase**: [eg. MVP 1: Foundation]
- **Summary**: [One-line description]
- **Precedents**: [OSS/commercial patterns with links]
- **Steps**:
    1. [Sub-task 1]
    2. [Sub-task 2]
    3. etc.
- **Validation Plan**: [Tests, CLI, success metrics]
- **Documentation Impact**: [Configs, docs, changelogs to update]

---

## Final Notes

- Copilot Pro agent should never skip research, planning, documentation, or validation steps.
- All progress and technical debt must be tracked.
- Prioritize security and compliance in every agent and RAG component.

---
