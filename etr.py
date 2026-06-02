You're right. For documentation, demonstrations, or thesis defense, it's better to cite the **entire code block range** rather than a single line.

### Sort — Ascending / Descending

**Lines 369–380**

```python
@app.route("/dataset/sort", methods=["POST"])
def sort_dataset() -> Any:
    ...
    ascending = order == "asc"
    DATASET_STATE["df"] = df.sort_values(by=column, ascending=ascending)
    direction = "ascending" if ascending else "descending"
    flash(f"Sorted by '{column}' ({direction}).", "success")
```

---

### Filter — `==` Operator

**Lines 387–400**

```python
@app.route("/dataset/filter", methods=["POST"])
def filter_dataset() -> Any:
    ...
    parsed = _parse_value(value, series.dtype)
    if operator == "eq":
        mask = series == parsed
```

---

### Filter — Contains Text

**Lines 401–412**

```python
elif operator == "neq":
    ...
elif operator == "contains":
    mask = series.astype("string").str.contains(value, na=False)
```

---

### Match Count Flash Message

**Lines 414–418**

```python
_push_history(...)
result = df.loc[mask]
DATASET_STATE["df"] = result
flash(f"Filter applied — {len(result)} row(s) match.", "success")
```

---

### Convert String Column → Integer

**Lines 342–352**

```python
_push_history(f"convert '{column}' to {target}")
updated = df.copy()
series = updated[column]

if target == "int":
    updated[column] = pd.to_numeric(
        series,
        errors="raise"
    ).astype("Int64")
```

---

### Show Dtype Update in Schema Panel

**Lines 105–113**

```python
return [
    {
        "name": col,
        "dtype": str(df[col].dtype),
        "missing": int(missing[col]),
    }
    for col in df.columns
]
```

and displayed through

**Lines 201–202**

```python
summary = _dataset_summary(df)
columns = _column_summary(df)
```

---

### Text Formatting — Strip

**Lines 459–464**

```python
updated = df.copy()
series = updated[column].astype("string")

if action == "strip":
    updated[column] = series.str.strip()
```

---

### Text Formatting — Uppercase

**Lines 465–466**

```python
elif action == "upper":
    updated[column] = series.str.upper()
```

---

### Text Formatting — Lowercase

**Lines 467–468**

```python
elif action == "lower":
    updated[column] = series.str.lower()
```

---

### Group By Category Column + Count

**Lines 433–441**

```python
if agg_func == "sum":
    ...
elif agg_func == "mean":
    ...
else:
    grouped = df.groupby(
        group_col,
        as_index=False
    )[agg_col].count()

    grouped.rename(
        columns={agg_col: f"{agg_col}_count"},
        inplace=True
    )
```

---

### Show Aggregated Result Table

**Lines 442–444**

```python
DATASET_STATE["df"] = grouped
flash(f"Grouped by '{group_col}' with {agg_func} of '{agg_col}'.", "success")
```

Then rendered by:

**Lines 202–206**

```python
preview = df.head(DISPLAY_LIMIT)
preview_rows = list(preview.iterrows())
truncated = df.shape[0] > DISPLAY_LIMIT
```

---

### Load to Database

**Lines 477–485**

```python
df = _require_dataset()
table_name = request.form.get("table_name", "").strip()

if not table_name:
    raise ValueError("Provide a table name.")

df.to_sql(
    table_name,
    con=engine,
    if_exists="replace",
    index=False
)
```

---

### Redirect to `/db`

**Lines 485–486**

```python
flash(...)
return redirect(
    url_for("db_view", table=table_name)
)
```

---

### Click Table and Show Data

**Lines 493–502**

```python
tables = inspector.get_table_names()
selected = request.args.get("table")

if selected and selected in tables:
    query = text(
        f"SELECT * FROM {selected} LIMIT {DISPLAY_LIMIT}"
    )
    preview = pd.read_sql_query(query, engine)
```

These ranges are what I'd put in a project report or defense slide because they cover the complete implementation of each requirement, not just the single statement that performs the action.
