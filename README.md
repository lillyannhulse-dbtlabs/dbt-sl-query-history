# dbt Semantic Layer Query History

Pulls query history from the dbt Semantic Layer GraphQL API and reports which
metrics were queried, how often, and by what connection, over a given time
window (defaults to the last full calendar month).

## Setup

1. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Fill in `.env` with your own values (this file is tracked empty in the
   repo — do not commit your real credentials after filling it in):

   ```
   DBT_API_KEY=your-service-token
   DBT_ACCOUNT_ID=your-account-id
   DBT_ENVIRONMENT_ID=your-environment-id
   DBT_SL_URL=https://<your-subdomain>.semantic-layer.<region>.dbt.com/api/graphql
   ```

   Find your Semantic Layer GraphQL URL here:
   https://docs.getdbt.com/docs/dbt-cloud-apis/sl-graphql#dbt-semantic-layer-graphql-api

3. Run it:

   ```
   python query_history.py
   ```

## What it does

- Pages through all `queryRecords` for your environment (the API has no
  server-side date filter, so this script fetches everything and filters
  client-side).
- Filters to the last full calendar month by default — edit
  `FILTER_START` / `FILTER_END` in `query_history.py` for a custom range.
- Prints per-query detail (status, timing, dialect, connection, metrics,
  group-by, filters) and a summary count of unique metrics queried.

## Note on attribution

The Semantic Layer API authenticates via a shared service token, so
`connectionDetails` on each record identifies the *calling integration*
(e.g. a BI tool), not necessarily an individual end user. For per-user
attribution you'd need your BI tool's own logs or dbt Cloud's audit log
(Enterprise plans).
