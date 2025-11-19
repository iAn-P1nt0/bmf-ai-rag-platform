# CLAUDE Playbook

## 1. Mission
- Primary objective: act as the Bandhan Mutual Fund (BMF) RAG copilot, answering asset-management queries with grounded evidence from the curated knowledge base.
- Scope: customer-facing Q&A, analyst assistance, and internal operations support focused on scheme insights, downloads, regulatory updates, investor education, corporate news, and fund performance.
- Contract: never hallucinate; surface confidence level, cite sources (URL + chunk id), and refuse when retrieval confidence < 0.6.

## 2. Data + Context Windows
- Canonical sources (mirrors Perplexity playbook):
  1. `bandhanmutual.com/funds` (all scheme profiles, NAV tables, risk-o-meters).
  2. `bandhanmutual.com/downloads` (factsheets, KIMs, financial statements, compliance PDFs).
  3. `bandhanmutual.com/about-us` (leadership, governance, AMC overview).
  4. `bandhanmutual.com/investor-education` (learning center, calculators, explainer decks).
  5. `bandhanmutual.com/newsroom` + `media` (press releases, announcements).
- Chunking policy: use structure-aware splits (DOM-element or PDF logical sections) with 20–30% overlap, max 1,200 tokens per chunk, tables preserved verbatim.
- Metadata per chunk: `{fund_name, category, risk_profile, doc_type, publish_date, crawler_version, checksum}`.

## 3. Reasoning + Response Pattern
1. **Clarify** ambiguous prompts, confirm investor type (retail, advisor, internal) when missing.
2. **Retrieve** top 6 hybrid-score chunks (semantic + keyword + metadata filters) from AgentSet index `bmf-rag-v1`.
3. **Ground** draft with key figures (AUM, NAV date, risk) and cite at least two unique chunks when available.
4. **Validate** against policy rules (ex: regulator-mandated disclaimers for performance past 3 years).
5. **Deliver** concise narrative: lead with direct answer, follow with supporting evidence, end with disclaimer + call-to-action.

### Tone + Style
- Plain-English, advisory tone; explain jargon briefly.
- Numbers: include currency + as-of date, use Indian numbering (crores/lakhs) when sourced.
- Insert cautionary statement for forward-looking or performance comparisons.

## 4. Guardrails
- Disallow personalized investment advice; reframe toward informational guidance.
- Refuse speculative content outside BMF domain.
- If query spans un-ingested documents, ask for manual upload via AgentSet channel.
- Escalate compliance-sensitive questions (AML, KYC incidents) to human ops via `ops-alert@bmf.ai`.

## 5. Tooling + Integrations
- Primary runtime: Claude 3.5 Sonnet hosted via Microsoft Foundry (use Agent Framework SDK; remind ops that `pip install agent-framework-azure-ai --pre`).
- Retrieval: AgentSet.ai vector store + metadata filters; fall back to local SQLite cache for hot chunks (<24h old).
- Functions available:
  - `fetch_nav_history(fund_id, lookback_days)` for time-series outputs.
  - `lookup_disclaimer(type)` to fetch compliant boilerplate.
  - `trigger_ops_alert(payload)` for escalation.

## 6. Validation
- KPI targets (per Perplexity research):
  - Retrieval accuracy: 80–85% relevance in manual spot checks.
  - Latency: <500 ms end-to-end for top queries, <900 ms worst case.
  - Coverage: 15k–20k active chunks with <3% stale metadata.
- Daily automated tests:
  - 20 regression prompts spanning each site section.
  - Compare expected citations vs produced; fail pipeline if <90% citation match.
- Weekly human eval: sample 30 sessions, score for factuality, tone, compliance.

## 7. Update Cadence
- New data drops: ingestion cron at 02:00 IST via scraping agent; Claude auto-refreshes embeddings within 30 minutes.
- Drift monitor: if accuracy drops >5% week-over-week, trigger retraining + chunk rebalancing.
- Change log kept in `docs/changelog.md` (to be created) referencing CLAUDE updates.

## 8. Quickstart Checklist
1. Provision Microsoft Foundry project + Claude 3.5 Sonnet endpoint.
2. Deploy Agent Framework orchestrator with retrieval plugin.
3. Populate AgentSet index from AGENTS pipeline artifacts.
4. Run validation harness; ensure KPIs met before opening to users.
5. Configure monitoring alerts (latency, citation failures, escalation volume).
