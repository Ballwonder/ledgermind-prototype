# LedgerMind v0.23 — Evidence Retrieval Orchestrator

Before creating an owner exception, LedgerMind now:
1. checks mapped evidence sources,
2. scans unprocessed source documents,
3. extracts document fields,
4. scores transaction matches,
5. auto-links only high-confidence matches,
6. runs the document validator,
7. reruns evidence sufficiency,
8. asks the owner only if support remains insufficient.

The sandbox uses a SourceDocument table to simulate email/receipt inboxes.

Production connectors are still separate:
- Gmail / Outlook retrieval
- uploads / receipt inbox
- cloud-document sources

Ambiguous matches are never auto-linked.
