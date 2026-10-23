# Wiki

Cross-project synthesized knowledge lives here.

## Support runbooks

Store a runbook as Markdown under `wiki/` with these frontmatter fields:

```yaml
---
type: runbook
review_status: reviewed
symptoms: "What the user or system reports"
cause: "Verified cause"
resolution: "Safe resolution steps"
escalation_boundary: "When to stop and escalate"
source_links: ["https://docs.example/support", "[[related-note]]"]
---
# Runbook title
Add diagnostic details and Markdown links here.
```

Recall returns a resolution only when `review_status` is exactly `reviewed` and
at least one source link is present. Draft or unreviewed runbooks remain
searchable, but their resolution is withheld. Source links can use the
`source_links` frontmatter list or Markdown/Obsidian links in the document.
