# Markdown-aware PR ownership references

- **Date:** 2026-07-28T17:36:00+02:00
- **By:** Switch
- **Decision:** The CI ownership gate recognizes unique closing references only in genuine top-level Markdown prose. Code spans, fenced and indented code blocks, blockquotes, and Markdown tables are documentation/quotation and do not close issues. The gate remains fail-closed: exactly one unique issue is required.
- **Security:** The PR body remains environment-backed and is never interpolated into the workflow run script.
- **Why:** Plain text matching counted documented syntax as issue closures and rejected valid PRs.
