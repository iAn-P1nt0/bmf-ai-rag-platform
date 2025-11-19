# BMF RAG Platform - Changelog

All notable changes to this project will be documented in this file per AGENTS.md Section 7.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### To Be Implemented
- Parser Agent with Unstructured.io integration
- Chunk Orchestrator with AgentSet SDK
- Validator Agent with Great Expectations
- Monitoring Agent with Prometheus/Grafana metrics
- Production AgentSet vector store integration
- S3 bucket configuration for raw/processed data
- Azure AI Claude hosting integration

## [0.1.0] - 2025-01-19

### Added
- Initial platform structure and architecture
- CLAUDE.md playbook defining RAG copilot behavior
- AGENTS.md playbook defining pipeline architecture
- Discovery Agent for URL tracking and site structure monitoring
- Scraper Agent with Playwright for dynamic page rendering
- Document Harvester for PDF/document downloads
- Claude RAG Copilot with 5-step reasoning pattern:
  1. Clarify (investor type detection)
  2. Retrieve (hybrid semantic search)
  3. Ground (citation-backed responses)
  4. Validate (compliance rules)
  5. Deliver (confidence-scored answers)
- Configuration system:
  - SITE_MAP.json for URL patterns and selectors
  - chunking.yml for semantic chunking rules
  - metadata_schema.json for chunk metadata validation
  - alerts.yml for KPI thresholds and alerting
- Airflow DAG for pipeline orchestration
- Management CLI (manage.py) for platform operations
- Regression test suite with 20 prompts covering all sections
- Deployment script (scripts/deploy.sh)
- Comprehensive README documentation

### Configuration
- Confidence threshold: 0.6 (refuse below)
- Retrieval accuracy target: 80-85%
- Latency targets: <500ms (P95), <900ms (critical)
- Citation match rate: >90%
- Coverage: 15k-20k active chunks
- Stale metadata threshold: <3%
- Chunking: max 1,200 tokens, 20-30% overlap
- Rate limit: 2 requests/second for scraping

### Compliance Features
- Past performance disclaimers
- Risk disclosure statements
- Personalized advice refusal
- KYC reminders
- Indian numbering format (crores/lakhs)
- As-of dates for all figures

### Data Pipeline
- Discovery: Daily 00:30 IST
- Scraper: Daily 02:00 IST
- Harvester: Daily 02:30 IST
- Parser: Daily 03:00 IST (pending implementation)
- Chunker: Daily 03:30 IST (pending implementation)
- Validator: Daily 04:00 IST (pending implementation)
- Monitoring: 24/7 (pending implementation)

### Quality Assurance
- SHA-256 checksums for deduplication
- Metadata completeness validation
- Automated regression testing
- Citation coverage verification
- Confidence threshold enforcement

## Version Guidelines

### Version Numbering
- Major.Minor.Patch (Semantic Versioning)
- Major: Breaking changes to API or architecture
- Minor: New features, agent implementations
- Patch: Bug fixes, configuration updates

### Change Categories
- **Added**: New features, agents, capabilities
- **Changed**: Modifications to existing functionality
- **Deprecated**: Features marked for removal
- **Removed**: Deleted features or code
- **Fixed**: Bug fixes
- **Security**: Security-related changes
- **Configuration**: Changes to config schemas or defaults
- **Performance**: Performance improvements

## Release Checklist

Before each release:
1. [ ] Update version number in this file
2. [ ] Run full test suite: `pytest tests/ -v`
3. [ ] Verify regression tests pass: >90% citation match
4. [ ] Check retrieval accuracy: 80-85% target
5. [ ] Validate configuration files
6. [ ] Update README if needed
7. [ ] Tag release in Git
8. [ ] Deploy to staging first
9. [ ] Run production validation
10. [ ] Monitor KPIs for 24 hours post-deployment

## Migration Notes

### Upgrading to 0.1.0
This is the initial release. Follow Quick Start guide in README.md

## Known Issues

### Current Limitations
- Parser, Chunk Orchestrator, Validator, and Monitoring agents not yet implemented
- AgentSet integration uses mock data for retrieval
- S3 storage optional (local storage default)
- No production monitoring dashboards yet
- Citation extraction relies on mock chunks

### Future Improvements
- Incremental diff scraping using ETag/Last-Modified headers (40% bandwidth reduction)
- MCP tools integration for structured financial data
- Anomaly detection for traffic spikes (Prophet)
- Automated regulatory bulletin ingestion
- Real-time chat interface for copilot
- Multi-language support (Hindi)

## Support & Contact

For questions about changes:
- Development: rag-team@bmf.ai
- Operations: ops-alert@bmf.ai

## References

- CLAUDE.md: RAG copilot specifications
- AGENTS.md: Pipeline architecture
- Perplexity Research: Performance benchmarks (80-85% accuracy, <500ms latency)
