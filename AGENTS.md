# AGENTS Architecture

## 1. Overview
- Purpose: orchestrate an end-to-end Bandhan Mutual Fund RAG pipeline (discovery, scraping, ingestion, monitoring) that feeds Claude with production-ready context.
- Stack alignment: Playwright-based crawlers, Unstructured.io parsers, Beautiful Soup validators, AgentSet.ai ingestion SDK, S3 (raw + processed), SQLite cache for rapid diffing, Airflow/cron scheduling.
- Performance guardrails inherited from Perplexity research: maintain 80–85% retrieval precision, <500 ms query latency, 15k–20k active chunks, <3% stale metadata.

## 2. Agent Roster
| Agent | Responsibilities | Key Tech | Schedule |
| --- | --- | --- | --- |
| **Discovery Agent** | Maintain `SITE_MAP` manifest of target sections (Funds, Downloads, About, Education, News). Detect new/changed URLs via heuristics + sitemaps. | Python, Requests, sitemap parser | Daily 00:30 IST |
| **Scraper Agent** | Render dynamic pages (React-heavy) with Playwright, respect robots + rate limits (2 rps/site). Persist raw HTML + screenshots. | Playwright, Rotating proxies, Redis rate limiter | Daily 02:00 IST + on-demand |
| **Document Harvester** | Download PDFs/KIMs/factsheets from `Downloads`, verify checksums. Push to `s3://bmf-rag/raw-pdf`. | AWS CLI, `wget`, checksum utility | Daily 02:30 IST |
| **Parser Agent** | Run Unstructured.io + custom table preservers to convert HTML/PDF into Markdown + JSON (tables, metrics). Apply semantic tagging (fund, risk, doc_type). | Unstructured, Pandas, Beautiful Soup | Follows scraping completion |
| **Chunk Orchestrator** | Build structure-aware chunks (max 1,200 tokens, 20–30% overlap) with metadata, push to AgentSet ingestion API. Tracks versioning + diff stats. | AgentSet SDK, SQLite diff DB | Daily 03:30 IST |
| **Validator Agent** | Sample 5% of new chunks; verify metadata completeness, run QA prompts, ensure citation coverage. | PyTest harness, Claude eval, Great Expectations | Daily 04:00 IST |
| **Monitoring Agent** | Watch KPI dashboards (latency, relevance, stale chunks). Alert if thresholds breached; trigger rollback or re-crawl. | Prometheus, Grafana, PagerDuty | 24x7 (5 min interval) |

## 3. Pipeline Flow
1. **Discovery** updates `SITE_MAP.json`; diff stored in Git tracked path `configs/site_map/`.
2. **Scraper** consumes manifest, captures HTML using Playwright headless Chromium with human-like delays, stores to `s3://bmf-rag/raw-html/{date}/`.
3. **Document Harvester** fetches linked PDFs, stores to raw bucket, records SHA256 for dedupe.
4. **Parser** converts assets to canonical formats (Markdown for narrative, JSON for tabular data) and attaches metadata.
5. **Chunk Orchestrator** applies semantic chunking + overlapping windows, enforces metadata schema, pushes to AgentSet index `bmf-rag-v1`.
6. **Validator** runs regression prompts + metadata integrity checks; fails pipeline if:
   - <90% chunks have mandatory metadata.
   - Retrieval eval <80% relevance.
   - Any compliance docs missing disclaimers.
7. **Monitoring** ingests telemetry, maintains drift baselines, and manages rollbacks.

## 4. Configuration Artifacts
- `configs/site_map/SITE_MAP.json`: section -> URL patterns + crawl frequency.
- `configs/chunking.yml`: token limits, overlap %, table handling rules.
- `configs/metadata_schema.json`: required fields + validation regex per field.
- `configs/alerts.yml`: KPI thresholds, notification channels, escalation tree.

## 5. Data Stores
- **S3 Raw**: `s3://bmf-rag/raw-html`, `s3://bmf-rag/raw-pdf` (immutable).
- **S3 Processed**: `s3://bmf-rag/processed/{yyyy-mm-dd}` storing Markdown/JSON outputs.
- **SQLite Diff DB**: tracks checksum history to avoid re-embedding unchanged chunks.
- **AgentSet Index**: production vector store powering Claude retrieval (hybrid search enabled).

## 6. Scheduling + Ops
- Default orchestrator: Airflow DAG `bmf_rag_pipeline` (tasks mirror agents above).
- Backfill mode: parameterize DAG with `start_date`, `end_date`, rerun discovery+scraper subset.
- On-demand refresh: CLI `python manage.py refresh --section funds --limit 5` triggers ad-hoc scrape.
- Secrets: stored in Azure Key Vault; agents fetch via managed identity.

## 7. Quality + Validation
- **Schema validation**: Great Expectations suite ensuring metadata completeness.
- **RAG regression**: 20 prompt set covering each site section run after every pipeline.
- **Human spot checks**: weekly review of 30 random chunks vs source documents.
- **Latency probe**: synthetic queries fired hourly; alert if >500 ms P95.

## 8. Incident Response
- Severity thresholds: relevance <75% (sev-2), latency >900 ms (sev-1), missing compliance doc (sev-0).
- Rollback process: restore previous AgentSet snapshot from `s3://bmf-rag/backups`, redeploy index, notify stakeholders.
- Communication: PagerDuty -> Slack `#bmf-rag-ops` -> email summary within 2 hours.

## 9. Future Enhancements
- Integrate MCP tools for structured financial data pulls.
- Add incremental diff scraper using ETag/Last-Modified headers to cut bandwidth 40%.
- Expand Monitoring Agent with anomaly detection (Prophet) for traffic spikes.
- Automate regulatory bulletin ingestion once RSS endpoints stabilized.
