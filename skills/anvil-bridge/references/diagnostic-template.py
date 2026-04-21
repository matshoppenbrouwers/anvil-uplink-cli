"""Diagnostic template — run with `anvil-bridge run /tmp/diag.py`.

Copy this to /tmp/diag.py, adapt the TABLE / column names to the target app,
then execute. The uplink connection is already live when the script starts.

Key facts about the runtime:
- `anvil` and `anvil.server` are pre-imported by the `run` command.
- `app_tables` is available via `from anvil.tables import app_tables`.
- `app_tables` is a lazy proxy — `dir(app_tables)` returns ['cache'], not table
  names. Reference tables directly: `app_tables.your_table_name`.
- Row objects need bracket access: `row['col']`, never `row.get('col')`.
- Iterating a row yields `[key, value]` pairs (a list, not a tuple).
"""
from collections import Counter
from statistics import mean, median

from anvil.tables import app_tables


def banner(title: str) -> None:
    print()
    print("===", title, "===")


# ---- EDIT BELOW: replace `your_table` with a real table from anvil.yaml ----

TABLE = "your_table"
NUMERIC_COL = "amount"
CATEGORY_COL = "status"

banner(f"{TABLE} — row count")
rows = list(app_tables[TABLE].search())
print("row_count:", len(rows))

banner(f"{TABLE} — {NUMERIC_COL} stats")
values = [r[NUMERIC_COL] for r in rows if r[NUMERIC_COL] is not None]
if values:
    print("count:", len(values))
    print("sum:", round(sum(values), 2))
    print("mean:", round(mean(values), 2))
    print("median:", round(median(values), 2))
    print("min:", round(min(values), 2))
    print("max:", round(max(values), 2))
else:
    print("no non-null values")

banner(f"{TABLE} — {CATEGORY_COL} distribution")
dist = Counter(r[CATEGORY_COL] for r in rows)
print(dict(dist))

banner("done")
