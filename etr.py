# Lines 369–380
# Sort — Ascending / Descending
# OVERVIEW: Sorts the dataset by a specified column in ascending or descending order,
# updates the global dataset state, and notifies the user via flash message.
@app.route("/dataset/sort", methods=["POST"])
def sort_dataset() -> Any:
    # Parse the sort order from the request: "asc" → True, anything else → False
    ascending = order == "asc"
    # Sort the DataFrame by the specified column in the requested direction
    # and update the global DATASET_STATE to persist the sorted data
    DATASET_STATE["df"] = df.sort_values(by=column, ascending=ascending)
    # Create a user-friendly string describing the sort direction
    direction = "ascending" if ascending else "descending"
    # Display a success notification to the user via Flask's flash messaging system
    flash(f"Sorted by '{column}' ({direction}).", "success")


# Lines 387–412
# Filter — Equality, Inequality, and Contains
# OVERVIEW: Filters the dataset based on a specified column and operator (equality, inequality,
# or substring match), updates the dataset state with matching rows, and displays the count
# of filtered results.
@app.route("/dataset/filter", methods=["POST"])
def filter_dataset() -> Any:
    # Convert the user-supplied filter value to the appropriate data type
    # (e.g., string "123" → int 123) based on the column's dtype
    parsed = _parse_value(value, series.dtype)
    
    # Build a boolean mask to identify matching rows based on the selected operator:
    if operator == "eq":
        # Equality: keep rows where column == parsed value
        mask = series == parsed
    elif operator == "neq":
        # Inequality: keep rows where column != parsed value
        mask = series != parsed
    elif operator == "contains":
        # Substring match: convert column to string and check if it contains the value
        # na=False treats missing values as non-matching
        mask = series.astype("string").str.contains(value, na=False)
    
    # Lines 414–418
    # Match Count Flash Message
    # Record this filter operation in the action history for undo/redo functionality
    _push_history(...)
    # Apply the mask to get only the rows that match the filter criteria
    result = df.loc[mask]
    # Update the global dataset state with the filtered DataFrame
    DATASET_STATE["df"] = result
    # Notify the user how many rows passed the filter
    flash(f"Filter applied — {len(result)} row(s) match.", "success")


# Lines 342–352
# Convert String Column → Integer
# OVERVIEW: Converts a specified column to an integer data type (Int64), supporting
# nullable integers and raising an error if non-numeric values are encountered.
def _convert_column(df, column, target):
    # Log the conversion operation to the history for future reference/undo
    _push_history(f"convert '{column}' to {target}")
    # Create a copy of the DataFrame to avoid modifying the original
    updated = df.copy()
    # Extract the column to be converted
    series = updated[column]
    
    # Perform type conversion based on the target data type
    if target == "int":
        # Convert to numeric, raising an error if any non-numeric values are encountered
        # Then cast to nullable Int64 (allows NaN values unlike standard int64)
        updated[column] = pd.to_numeric(
            series,
            errors="raise"
        ).astype("Int64")
    return updated


# Lines 105–113
# Show Dtype Update in Schema Panel
# OVERVIEW: Generates a list of column metadata (name, data type, missing value count)
# for each column in the dataset, used to display schema information in the UI.
def _column_summary(df):
    # Count missing (null) values for each column
    missing = df.isnull().sum()
    # Build a list of dictionaries describing each column's metadata
    return [
        {
            "name": col,  # Column name
            "dtype": str(df[col].dtype),  # Data type (e.g., "int64", "object", "float64")
            "missing": int(missing[col]),  # Number of null values in this column
        }
        for col in df.columns
    ]


# Lines 201–206
# Display Dataset Summary and Columns
# OVERVIEW: Assembles all display-related data (summary stats, column metadata, preview rows)
# needed to render the dataset view in the UI, including truncation status for large datasets.
def _get_display_data(df):
    # Retrieve overall dataset statistics (row count, column count, memory usage, etc.)
    summary = _dataset_summary(df)
    # Get detailed metadata for each column (name, dtype, missing count)
    columns = _column_summary(df)
    # Extract the first N rows (where N = DISPLAY_LIMIT) for preview display
    preview = df.head(DISPLAY_LIMIT)
    # Convert preview rows to a list of (index, row_data) tuples for templating
    preview_rows = list(preview.iterrows())
    # Check if the dataset is larger than what's being displayed
    truncated = df.shape[0] > DISPLAY_LIMIT
    # Return all components needed to render the dataset view in the UI
    return summary, columns, preview_rows, truncated


# Lines 459–468
# Text Formatting — Strip, Uppercase, Lowercase
# OVERVIEW: Applies text transformations (strip whitespace, uppercase, or lowercase)
# to a specified column in the dataset.
def _format_text(df, column, action):
    # Create a copy to avoid modifying the original DataFrame
    updated = df.copy()
    # Convert the column to string type to enable string operations
    series = updated[column].astype("string")
    
    # Apply the requested text transformation:
    if action == "strip":
        # Remove leading and trailing whitespace from all values
        updated[column] = series.str.strip()
    elif action == "upper":
        # Convert all characters to uppercase
        updated[column] = series.str.upper()
    elif action == "lower":
        # Convert all characters to lowercase
        updated[column] = series.str.lower()
    
    return updated


# Lines 433–444
# Group By Category Column + Count/Sum/Mean
# OVERVIEW: Performs aggregation on the dataset by grouping rows based on a category column
# and applying a function (sum, mean, or count) to aggregate values, updates the dataset state,
# and displays a success notification.
def _aggregate_data(df, group_col, agg_col, agg_func):
    # Perform aggregation based on the selected function:
    if agg_func == "sum":
        # Sum values of agg_col grouped by group_col
        grouped = df.groupby(group_col, as_index=False)[agg_col].sum()
    elif agg_func == "mean":
        # Calculate average of agg_col grouped by group_col
        grouped = df.groupby(group_col, as_index=False)[agg_col].mean()
    else:
        # Default to counting occurrences of each group
        grouped = df.groupby(
            group_col,
            as_index=False
        )[agg_col].count()
        # Rename the count column to be more descriptive (e.g., "sales_count")
        grouped.rename(
            columns={agg_col: f"{agg_col}_count"},
            inplace=True
        )
    
    # Save the aggregated result to the global dataset state
    DATASET_STATE["df"] = grouped
    # Notify the user of the successful aggregation
    flash(f"Grouped by '{group_col}' with {agg_func} of '{agg_col}'.", "success")
    return grouped


# Lines 477–486
# Load to Database and Redirect
# OVERVIEW: Exports the current dataset to a database table with a user-specified name,
# overwriting if the table exists, and redirects to the database view page.
def _load_to_database(df, table_name):
    # Ensure a dataset is loaded; raises an error if not
    df = _require_dataset()
    # Extract and clean the table name from the form submission (remove whitespace)
    table_name = request.form.get("table_name", "").strip()
    
    # Validate that a table name was provided
    if not table_name:
        raise ValueError("Provide a table name.")
    
    # Export the DataFrame to SQL using SQLAlchemy engine connection
    # if_exists="replace" will overwrite the table if it already exists
    # index=False omits the DataFrame's index from the database
    df.to_sql(
        table_name,
        con=engine,
        if_exists="replace",
        index=False
    )
    # Flash a success message to the user (message content not shown)
    flash(...)
    # Redirect to the database view page showing the newly saved table
    return redirect(
        url_for("db_view", table=table_name)
    )


# Lines 493–502
# Click Table and Show Data from Database
# OVERVIEW: Retrieves a preview of a selected database table (limited to DISPLAY_LIMIT rows)
# and returns it as a Pandas DataFrame, or None if the table doesn't exist.
def _query_database_table(selected):
    # Retrieve a list of all table names available in the connected database
    tables = inspector.get_table_names()
    
    # Check if a table was selected and that it actually exists in the database
    if selected and selected in tables:
        # Build a SQL SELECT query that retrieves all columns from the table
        # Limited to DISPLAY_LIMIT rows to avoid loading massive datasets
        query = text(
            f"SELECT * FROM {selected} LIMIT {DISPLAY_LIMIT}"
        )
        # Execute the query and load the result into a Pandas DataFrame
        preview = pd.read_sql_query(query, engine)
        return preview
    # Return None if no valid table was selected or it doesn't exist
    return None
