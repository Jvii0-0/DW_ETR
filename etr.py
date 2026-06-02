# Lines 369–380
# Sort — Ascending / Descending
@app.route("/dataset/sort", methods=["POST"])
def sort_dataset() -> Any:
    ascending = order == "asc"
    DATASET_STATE["df"] = df.sort_values(by=column, ascending=ascending)
    direction = "ascending" if ascending else "descending"
    flash(f"Sorted by '{column}' ({direction}).", "success")


# Lines 387–412
# Filter — Equality, Inequality, and Contains
@app.route("/dataset/filter", methods=["POST"])
def filter_dataset() -> Any:
    parsed = _parse_value(value, series.dtype)
    if operator == "eq":
        mask = series == parsed
    elif operator == "neq":
        mask = series != parsed
    elif operator == "contains":
        mask = series.astype("string").str.contains(value, na=False)
    
    # Lines 414–418
    # Match Count Flash Message
    _push_history(...)
    result = df.loc[mask]
    DATASET_STATE["df"] = result
    flash(f"Filter applied — {len(result)} row(s) match.", "success")


# Lines 342–352
# Convert String Column → Integer
def _convert_column(df, column, target):
    _push_history(f"convert '{column}' to {target}")
    updated = df.copy()
    series = updated[column]
    
    if target == "int":
        updated[column] = pd.to_numeric(
            series,
            errors="raise"
        ).astype("Int64")
    return updated


# Lines 105–113
# Show Dtype Update in Schema Panel
def _column_summary(df):
    missing = df.isnull().sum()
    return [
        {
            "name": col,
            "dtype": str(df[col].dtype),
            "missing": int(missing[col]),
        }
        for col in df.columns
    ]


# Lines 201–206
# Display Dataset Summary and Columns
def _get_display_data(df):
    summary = _dataset_summary(df)
    columns = _column_summary(df)
    preview = df.head(DISPLAY_LIMIT)
    preview_rows = list(preview.iterrows())
    truncated = df.shape[0] > DISPLAY_LIMIT
    return summary, columns, preview_rows, truncated


# Lines 459–468
# Text Formatting — Strip, Uppercase, Lowercase
def _format_text(df, column, action):
    updated = df.copy()
    series = updated[column].astype("string")
    
    if action == "strip":
        updated[column] = series.str.strip()
    elif action == "upper":
        updated[column] = series.str.upper()
    elif action == "lower":
        updated[column] = series.str.lower()
    
    return updated


# Lines 433–444
# Group By Category Column + Count/Sum/Mean
def _aggregate_data(df, group_col, agg_col, agg_func):
    if agg_func == "sum":
        grouped = df.groupby(group_col, as_index=False)[agg_col].sum()
    elif agg_func == "mean":
        grouped = df.groupby(group_col, as_index=False)[agg_col].mean()
    else:
        grouped = df.groupby(
            group_col,
            as_index=False
        )[agg_col].count()
        grouped.rename(
            columns={agg_col: f"{agg_col}_count"},
            inplace=True
        )
    
    DATASET_STATE["df"] = grouped
    flash(f"Grouped by '{group_col}' with {agg_func} of '{agg_col}'.", "success")
    return grouped


# Lines 477–486
# Load to Database and Redirect
def _load_to_database(df, table_name):
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
    flash(...)
    return redirect(
        url_for("db_view", table=table_name)
    )


# Lines 493–502
# Click Table and Show Data from Database
def _query_database_table(selected):
    tables = inspector.get_table_names()
    
    if selected and selected in tables:
        query = text(
            f"SELECT * FROM {selected} LIMIT {DISPLAY_LIMIT}"
        )
        preview = pd.read_sql_query(query, engine)
        return preview
    return None
