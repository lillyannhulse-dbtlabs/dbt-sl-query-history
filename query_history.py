import os
import requests
import json
from collections import Counter
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# -------------------------------
# Environment Variables
# -------------------------------
# Set these in your shell or in a .env file in this directory:
#
#   DBT_API_KEY="your-service-token"
#   DBT_ACCOUNT_ID="your-account-id"
#   DBT_ENVIRONMENT_ID="your-environment-id"
#   DBT_SL_URL="https://<your-subdomain>.semantic-layer.<region>.dbt.com/api/graphql"
# Find your Semantic Layer GraphQL URL here:
# https://docs.getdbt.com/docs/dbt-cloud-apis/sl-graphql#dbt-semantic-layer-graphql-api

DBT_API_KEY        = os.environ.get("DBT_API_KEY")
DBT_ACCOUNT_ID     = os.environ.get("DBT_ACCOUNT_ID")
DBT_ENVIRONMENT_ID = os.environ.get("DBT_ENVIRONMENT_ID")
DBT_SL_URL         = os.environ.get("DBT_SL_URL")

if not all([DBT_API_KEY, DBT_ACCOUNT_ID, DBT_ENVIRONMENT_ID, DBT_SL_URL]):
    raise EnvironmentError(
        "Missing one or more required env vars: "
        "DBT_API_KEY, DBT_ACCOUNT_ID, DBT_ENVIRONMENT_ID, DBT_SL_URL"
    )

# -------------------------------
# Date Range Filter
# -------------------------------
# The Semantic Layer API has no server-side date filtering, so we filter
# client-side on startTime after fetching. Defaults to the last full
# calendar month; change FILTER_START/FILTER_END below for a custom range.


def get_last_month_range():
    now = datetime.now(timezone.utc)
    start_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_of_this_month.month == 1:
        start_of_last_month = start_of_this_month.replace(year=start_of_this_month.year - 1, month=12)
    else:
        start_of_last_month = start_of_this_month.replace(month=start_of_this_month.month - 1)
    return start_of_last_month, start_of_this_month


FILTER_START, FILTER_END = get_last_month_range()

# -------------------------------
# GraphQL Query
# -------------------------------
PAGE_SIZE = 500


def build_query(page_num):
    return f"""
{{
  queryRecords(
    environmentId: {DBT_ENVIRONMENT_ID}
    pageSize: {PAGE_SIZE}
    pageNum: {page_num}
  ) {{
    items {{
      queryId
      status
      startTime
      endTime
      connectionDetails
      sqlDialect
      connectionSchema
      error
      queryDetails {{
        ... on SemanticLayerQueryDetails {{
          params {{
            type
            metrics {{
              name
            }}
            groupBy {{
              name
              grain
            }}
            limit
            where {{
              sql
            }}
            orderBy {{
              groupBy {{
                name
                grain
              }}
              metric {{
                name
              }}
              descending
            }}
            savedQuery
          }}
        }}
        ... on RawSqlQueryDetails {{
          queryStr
          compiledSql
          numCols
          queryDescription
          queryTitle
        }}
      }}
    }}
    totalItems
    pageNum
    pageSize
  }}
}}
"""


# -------------------------------
# Request
# -------------------------------
headers = {
    "Authorization": f"Bearer {DBT_API_KEY}",
    "Content-Type": "application/json",
}

# Page through all query records so results aren't truncated to a single
# response page.
all_records = []
graphql_errors = None
page_num = 1
total_items = None

while True:
    response = requests.post(DBT_SL_URL, headers=headers, json={"query": build_query(page_num)})
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        graphql_errors = data["errors"]
        break

    page = data["data"]["queryRecords"]
    all_records.extend(page["items"])
    total_items = page["totalItems"]

    if not page["items"] or len(all_records) >= total_items:
        break
    page_num += 1

# -------------------------------
# Parse & Display
# -------------------------------
if graphql_errors is not None:
    print("GraphQL Errors:", json.dumps(graphql_errors, indent=2))
else:
    print(f"Fetched {len(all_records)} of {total_items} total query records across {page_num} page(s).\n")

    def in_filter_range(record):
        start_time = record.get("startTime")
        if not start_time:
            return False
        parsed = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        return FILTER_START <= parsed < FILTER_END

    records = [r for r in all_records if in_filter_range(r)]
    print(f"✅ Retrieved {len(all_records)} query records total; "
          f"{len(records)} fall within {FILTER_START.date()} to {FILTER_END.date()}.\n")

    metric_counts = Counter()

    for r in records:
        print("=" * 80)
        print(f"Query ID: {r.get('queryId')}")
        print(f"Status: {r.get('status')}")
        print(f"Start Time: {r.get('startTime')}")
        print(f"End Time: {r.get('endTime')}")
        print(f"SQL Dialect: {r.get('sqlDialect')}")
        print(f"Connection: {r.get('connectionSchema')}")

        connection_details = r.get("connectionDetails")
        if isinstance(connection_details, str):
            try:
                connection_details = json.loads(connection_details)
            except (TypeError, ValueError):
                pass
        print(f"Called By (connectionDetails): {connection_details}")

        if r.get("error"):
            print(f"⚠️ Error: {r['error']}")
        if (
            r.get("queryDetails")
            and isinstance(r["queryDetails"], dict)
            and "params" in r["queryDetails"]
        ):
            params = r["queryDetails"]["params"]
            metrics = [m["name"] for m in params.get("metrics", [])]
            metric_counts.update(metrics)
            group_by = params.get("groupBy") or []
            where_clauses = params.get("where") or []

            print(f"Metrics: {metrics}")
            if group_by:
                print(f"Group By: {[g['name'] for g in group_by if g]}")
            if where_clauses:
                print(f"Where: {[w['sql'] for w in where_clauses if w.get('sql')]}")
        print("=" * 80)
        print()

    total_metric_queries = sum(metric_counts.values())
    print(f"Total metrics queried (across all records): {total_metric_queries}")
    print(f"Unique metrics queried: {len(metric_counts)}")
    for name, count in metric_counts.most_common():
        print(f"  {name}: {count}")
