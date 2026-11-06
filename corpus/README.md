# Seed corpus

Development seed documents for IncCorpAI. They summarise public statutes and official guidance
as of `last_reviewed`, but they are **not legal advice and not a substitute for the primary
sources** linked in each file's `source_url`. Fees, thresholds and deadlines change by
notification — re-verify before relying on them, and replace or extend these files with the
official PDFs for production use.

## Adding a document

Markdown files carry metadata in YAML front-matter:

```yaml
---
title: Human readable title
jurisdiction: IN            # IN | US-DE | EU  (see app/core/taxonomy.py)
entity_type: [Pvt Ltd, LLP] # one value, a list, or "Any"
regulatory_body: MCA
compliance_phase: Incorporation
source_url: https://...
last_reviewed: 2026-11-06
---
```

Headings can override metadata for their subtree:

```markdown
## SPICe+ Part A {clause="SPICe+ Part A" phase="Pre-Incorporation"}
```

PDF and TXT files take metadata from a sidecar `<file>.pdf.meta.json` with the same keys.

Then run `python ingest.py ../corpus` from `backend/`. Unchanged files are skipped by checksum.
