# Live dashboard (BigQuery → Claude artifact)

`live.html` is the Practice Pulse page with no data baked in. When it opens inside Claude it runs
five read-only queries against the BigQuery warehouse through the viewer's own
**Google Cloud BigQuery** connector (`execute_sql_readonly`, polling `get_query_results` for slow jobs):

| Piece  | Query file | What it fills |
|--------|------------|---------------|
| core   | core.sql   | offices, monthly totals, source row counts, unmapped codes |
| detail | detail.sql | marketing channels, procedure mix, GL reconciliation |
| opex0–2| opex.sql   | expense line items, 6 months per chunk (latest first) |

Rebuild after changing the template or SQL: `python build_live.py [gcp-project-id]`.

Notes
- Results are cached 5 minutes fresh / 24 hours replay per viewer; "Refresh data" re-runs the queries.
- Each full load scans roughly 0.6–0.8 GB of the 1 TB/month free query allowance.
- Each viewer needs the BigQuery connector and read access to the GCP project; the page can't be shared publicly.
- Test location 99 (a connector test account) is excluded from every query.
