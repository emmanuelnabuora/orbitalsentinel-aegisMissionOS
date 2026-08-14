# ADR-0009: Reporting — immutable snapshots from live data, PDF export

## Status
Accepted — Phase 8. Closes the last MVP placeholder.

## Context
Leadership and mission partners need point-in-time reports (executive summary,
mission assurance, incident, threat intel, quantum readiness). A report cited in
a review or shared with an agency must render identically forever — it cannot
silently change when the underlying data moves.

## Decisions

### 1. Reports are immutable snapshots
Generating a report reads current state through the same services the UI uses
and writes a `Report` row whose `content` is a self-contained structured JSON
document. Regeneration creates a new row; existing reports are never mutated.
A report referenced in an audit or an email is reproducible byte-for-byte.

### 2. Structured content, multiple renderers
`content` is `{summary, sections[]}` where each section carries a heading plus
prose and/or a table. This separates *what the report says* from *how it's
rendered*. The API returns JSON (the UI previews it); the PDF renderer
(`report_pdf.py`, reportlab) turns the same structure into an AEGIS-themed
document. HTML/DOCX renderers could be added over the identical content.

### 3. Narrative by SentinelAI, facts assembled deterministically
The summary prose comes from SentinelAI (rule-based or LLM, per configuration);
tables and figures are assembled here from live data. Provenance (`provider`)
is stored and printed, so a reader knows how the narrative was produced.

### 4. reportlab, not a headless browser
PDF generation uses reportlab: pure-Python, no Chromium/WeasyPrint system
dependencies, works in the same locked-down container as the API. Appropriate
for an air-gapped or IL4+ deployment where installing a browser is a liability.

## Test-suite lesson (again, and decisively)
The report builders initially passed `actor_id=uuid.uuid4()` when calling
SentinelAI sub-operations, which write audit records. On sqlite (FKs off) this
passed; PostgreSQL rejected the orphaned `audit_log.actor_id`. This was a **real
bug** — it would have written audit rows attributed to non-existent users in
production. Fixed by threading the true actor through every builder. Third time
the dual-dialect suite has caught an integrity assumption sqlite hid; the
both-dialects CI gate has paid for itself.
