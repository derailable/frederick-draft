# Weekly workflow

1. Run `uv run frederick-draft fetch`. Failures are expected to be reviewed, not bypassed.
2. Review changed easy sources and the configured manual draft sources. A typical update should take
   about 15–20 minutes.
3. Follow the extraction prompts and replace the ignored candidate JSON files. Do not edit public
   CSVs.
4. Run `uv run frederick-draft validate`, then `uv run frederick-draft accept`.
5. Run `uv run frederick-draft metrics`, tests, and Ruff.
6. Review `git status`; commit only reference/public structured data and code changes.

A failed, partial, or uncertain draft source must not close existing tap runs. Mark `complete_list`
true only for a successfully fetched, clearly complete current tap menu. Manual and partial sources
may supply positive observations with `complete_list` false.
