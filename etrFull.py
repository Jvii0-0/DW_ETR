import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, url_for
from sqlalchemy import create_engine, inspect, text
from werkzeug.utils import secure_filename

APP_TITLE = "ETL Data Workshop"
UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
DISPLAY_LIMIT = 200
UNDO_LIMIT = 20

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///etl_demo.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "etl-demo-secret")

engine = create_engine(DATABASE_URL, future=True)

DATASET_STATE: Dict[str, Any] = {
    "df": None,
    "original": None,
    "name": None,
    "source": None,
    "history": [],  # list of (df_snapshot, label) tuples
}


def _set_dataset(df: pd.DataFrame, name: str, source: str) -> None:
    DATASET_STATE["df"] = df
    DATASET_STATE["original"] = df.copy()
    DATASET_STATE["name"] = name
    DATASET_STATE["source"] = source
    DATASET_STATE["history"] = []


def _get_dataset() -> Optional[pd.DataFrame]:
    return DATASET_STATE.get("df")


def _require_dataset() -> pd.DataFrame:
    df = _get_dataset()
    if df is None:
        raise ValueError("No dataset loaded. Upload a file first.")
    return df


def _push_history(label: str) -> None:
    """Save current df snapshot before a destructive operation."""
    df = DATASET_STATE.get("df")
    if df is None:
        return
    history = DATASET_STATE["history"]
    history.append((df.copy(), label))
    if len(history) > UNDO_LIMIT:
        history.pop(0)


def _can_undo() -> bool:
    return len(DATASET_STATE["history"]) > 0


def _undo_label() -> Optional[str]:
    if _can_undo():
        return DATASET_STATE["history"][-1][1]
    return None


def _allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in UPLOAD_EXTENSIONS


def _load_file(file_storage) -> Tuple[pd.DataFrame, str]:
    filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(filename.lower())
    if ext == ".csv":
        df = pd.read_csv(file_storage)
    elif ext in {".xlsx", ".xls"}:
        df = pd.read_excel(file_storage)
    elif ext == ".json":
        raw = file_storage.read()
        text_data = raw.decode("utf-8")
        try:
            df = pd.read_json(text_data)
        except ValueError:
            data = json.loads(text_data)
            df = pd.DataFrame(data)
    else:
        raise ValueError("Unsupported file type.")
    return df, filename


def _dataset_summary(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_total": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }


def _column_summary(df: pd.DataFrame) -> List[Dict[str, Any]]:
    missing = df.isna().sum()
    return [
        {
            "name": col,
            "dtype": str(df[col].dtype),
            "missing": int(missing[col]),
        }
        for col in df.columns
    ]


def _parse_value(raw: str, dtype: Any) -> Any:
    if pd.api.types.is_numeric_dtype(dtype):
        return pd.to_numeric(raw, errors="raise")
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return pd.to_datetime(raw, errors="raise")
    return raw


def _apply_missing_action(df: pd.DataFrame, action: str, constant: Optional[str]) -> pd.DataFrame:
    if action == "drop_rows":
        return df.dropna()
    if action == "drop_columns":
        return df.dropna(axis=1)
    if action == "impute_mean":
        updated = df.copy()
        numeric_cols = updated.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            updated[numeric_cols] = updated[numeric_cols].fillna(updated[numeric_cols].mean())
        for col in updated.columns.difference(numeric_cols):
            mode = updated[col].mode(dropna=True)
            if not mode.empty:
                updated[col] = updated[col].fillna(mode.iloc[0])
        return updated
    if action == "impute_median":
        updated = df.copy()
        numeric_cols = updated.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            updated[numeric_cols] = updated[numeric_cols].fillna(updated[numeric_cols].median())
        for col in updated.columns.difference(numeric_cols):
            mode = updated[col].mode(dropna=True)
            if not mode.empty:
                updated[col] = updated[col].fillna(mode.iloc[0])
        return updated
    if action == "impute_mode":
        updated = df.copy()
        for col in updated.columns:
            mode = updated[col].mode(dropna=True)
            if not mode.empty:
                updated[col] = updated[col].fillna(mode.iloc[0])
        return updated
    if action == "impute_constant":
        if constant is None or constant.strip() == "":
            raise ValueError("Provide a constant value for imputation.")
        return df.fillna(constant)
    raise ValueError("Unknown missing value action.")


@app.route("/", methods=["GET", "POST"])
def index() -> Any:
    if request.method == "POST":
        file = request.files.get("file")
        if file is None or file.filename == "":
            flash("Please choose a dataset file.", "warning")
            return redirect(url_for("index"))
        if not _allowed_file(file.filename):
            flash("Only CSV, Excel, or JSON files are supported.", "warning")
            return redirect(url_for("index"))
        try:
            df, filename = _load_file(file)
            _set_dataset(df, filename, "upload")
            flash(f"Loaded '{filename}' — {df.shape[0]} rows, {df.shape[1]} columns.", "success")
            return redirect(url_for("dataset"))
        except Exception as exc:
            flash(f"Error loading file: {str(exc)}", "danger")
            return redirect(url_for("index"))

    df = _get_dataset()
    summary = _dataset_summary(df) if df is not None else None
    columns = _column_summary(df) if df is not None else None
    return render_template(
        "index.html",
        app_title=APP_TITLE,
        dataset=DATASET_STATE,
        summary=summary,
        columns=columns,
    )


@app.route("/dataset")
def dataset() -> Any:
    df = _get_dataset()
    if df is None:
        flash("Upload a dataset to start working.", "warning")
        return redirect(url_for("index"))
    summary = _dataset_summary(df)
    columns = _column_summary(df)
    preview = df.head(DISPLAY_LIMIT)
    preview_rows = list(preview.iterrows())
    truncated = df.shape[0] > DISPLAY_LIMIT
    return render_template(
        "dataset.html",
        app_title=APP_TITLE,
        dataset=DATASET_STATE,
        summary=summary,
        columns=columns,
        preview_columns=preview.columns,
        preview_rows=preview_rows,
        truncated=truncated,
        can_undo=_can_undo(),
        undo_label=_undo_label(),
    )


@app.route("/dataset/undo", methods=["POST"])
def undo_last() -> Any:
    if not _can_undo():
        flash("Nothing to undo.", "warning")
        return redirect(url_for("dataset"))
    df_snapshot, label = DATASET_STATE["history"].pop()
    DATASET_STATE["df"] = df_snapshot
    flash(f"Undid: {label}", "success")
    return redirect(url_for("dataset"))


@app.route("/dataset/reset", methods=["POST"])
def reset_dataset() -> Any:
    original = DATASET_STATE.get("original")
    if original is None:
        flash("No dataset to reset.", "warning")
        return redirect(url_for("index"))
    _push_history("before full reset")
    DATASET_STATE["df"] = original.copy()
    DATASET_STATE["history"] = []
    flash("Dataset reset to the original upload.", "success")
    return redirect(url_for("dataset"))


@app.route("/dataset/duplicates", methods=["POST"])
def remove_duplicates() -> Any:
    try:
        df = _require_dataset()
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("index"))
    before = len(df)
    _push_history("remove duplicates")
    DATASET_STATE["df"] = df.drop_duplicates()
    after = len(DATASET_STATE["df"])
    flash(f"Removed {before - after} duplicate row(s).", "success")
    return redirect(url_for("dataset"))


@app.route("/dataset/missing", methods=["POST"])
def handle_missing() -> Any:
    try:
        df = _require_dataset()
        action = request.form.get("missing_action", "")
        constant = request.form.get("missing_constant") or None
        _push_history(f"handle missing ({action})")
        DATASET_STATE["df"] = _apply_missing_action(df, action, constant)
        flash("Missing values handled.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/delete", methods=["POST"])
def delete_selection() -> Any:
    try:
        df = _require_dataset()
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("index"))
    action = request.form.get("delete_action")
    updated = df.copy()
    if action == "rows":
        rows = request.form.getlist("row_select")
        if not rows:
            flash("No rows selected.", "warning")
            return redirect(url_for("dataset"))
        _push_history(f"delete {len(rows)} row(s)")
        if pd.api.types.is_integer_dtype(updated.index):
            row_ids = [int(r) for r in rows]
        elif pd.api.types.is_float_dtype(updated.index):
            row_ids = [float(r) for r in rows]
        elif pd.api.types.is_datetime64_any_dtype(updated.index):
            row_ids = [pd.to_datetime(r, errors="raise") for r in rows]
        else:
            row_ids = rows
        updated = updated.drop(index=row_ids)
        flash(f"Deleted {len(row_ids)} row(s).", "success")
    elif action == "columns":
        cols = request.form.getlist("col_select")
        if not cols:
            flash("No columns selected.", "warning")
            return redirect(url_for("dataset"))
        _push_history(f"delete columns: {', '.join(cols)}")
        updated = updated.drop(columns=cols)
        flash(f"Deleted {len(cols)} column(s).", "success")
    else:
        flash("Choose rows or columns to delete.", "warning")
    DATASET_STATE["df"] = updated
    return redirect(url_for("dataset"))


@app.route("/dataset/replace", methods=["POST"])
def replace_values() -> Any:
    try:
        df = _require_dataset()
        column = request.form.get("replace_column")
        old_value = request.form.get("replace_old")
        new_value = request.form.get("replace_new")
        if not old_value and old_value != "0":
            raise ValueError("Provide an old value to replace.")
        if new_value is None:
            raise ValueError("Provide a new value.")
        _push_history(f"replace '{old_value}' → '{new_value}'")
        updated = df.copy()
        if column and column in updated.columns:
            updated[column] = updated[column].replace(old_value, new_value)
            flash(f"Replaced '{old_value}' with '{new_value}' in column '{column}'.", "success")
        else:
            updated = updated.replace(old_value, new_value)
            flash(f"Replaced '{old_value}' with '{new_value}' across all columns.", "success")
        DATASET_STATE["df"] = updated
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/convert", methods=["POST"])
def convert_types() -> Any:
    try:
        df = _require_dataset()
        column = request.form.get("convert_column")
        target = request.form.get("convert_type")
        if not column or column not in df.columns:
            raise ValueError("Choose a valid column to convert.")
        if not target:
            raise ValueError("Choose a data type to convert to.")
        _push_history(f"convert '{column}' to {target}")
        updated = df.copy()
        series = updated[column]
        if target == "int":
            updated[column] = pd.to_numeric(series, errors="raise").astype("Int64")
        elif target == "float":
            updated[column] = pd.to_numeric(series, errors="raise")
        elif target == "string":
            updated[column] = series.astype("string")
        elif target == "datetime":
            updated[column] = pd.to_datetime(series, errors="raise")
        else:
            raise ValueError("Unsupported conversion type.")
        DATASET_STATE["df"] = updated
        flash(f"Column '{column}' converted to {target}.", "success")
    except (ValueError, TypeError) as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/sort", methods=["POST"])
def sort_dataset() -> Any:
    try:
        df = _require_dataset()
        column = request.form.get("sort_column")
        order = request.form.get("sort_order", "asc")
        if not column or column not in df.columns:
            raise ValueError("Choose a valid column to sort by.")
        _push_history(f"sort by '{column}' {order}")
        ascending = order == "asc"
        DATASET_STATE["df"] = df.sort_values(by=column, ascending=ascending)
        direction = "ascending" if ascending else "descending"
        flash(f"Sorted by '{column}' ({direction}).", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/filter", methods=["POST"])
def filter_dataset() -> Any:
    try:
        df = _require_dataset()
        column = request.form.get("filter_column")
        operator = request.form.get("filter_operator")
        value = request.form.get("filter_value")
        if not column or column not in df.columns:
            raise ValueError("Choose a valid column to filter.")
        if not operator or value is None:
            raise ValueError("Provide a filter operator and value.")
        series = df[column]
        parsed = _parse_value(value, series.dtype)
        if operator == "eq":
            mask = series == parsed
        elif operator == "neq":
            mask = series != parsed
        elif operator == "gt":
            mask = series > parsed
        elif operator == "gte":
            mask = series >= parsed
        elif operator == "lt":
            mask = series < parsed
        elif operator == "lte":
            mask = series <= parsed
        elif operator == "contains":
            mask = series.astype("string").str.contains(value, na=False)
        else:
            raise ValueError("Unsupported filter operator.")
        _push_history(f"filter '{column}' {operator} '{value}'")
        result = df.loc[mask]
        DATASET_STATE["df"] = result
        flash(f"Filter applied — {len(result)} row(s) match.", "success")
    except (ValueError, TypeError) as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/groupby", methods=["POST"])
def group_by() -> Any:
    try:
        df = _require_dataset()
        group_col = request.form.get("group_column")
        agg_col = request.form.get("agg_column")
        agg_func = request.form.get("agg_func", "count")
        if not group_col or group_col not in df.columns:
            raise ValueError("Select a valid column to group by.")
        if not agg_col or agg_col not in df.columns:
            raise ValueError("Select a valid column to aggregate.")
        _push_history(f"group by '{group_col}' {agg_func}('{agg_col}')")
        if agg_func == "sum":
            grouped = df.groupby(group_col, as_index=False)[agg_col].sum()
        elif agg_func == "mean":
            grouped = df.groupby(group_col, as_index=False)[agg_col].mean()
        else:
            grouped = df.groupby(group_col, as_index=False)[agg_col].count()
            grouped.rename(columns={agg_col: f"{agg_col}_count"}, inplace=True)
        DATASET_STATE["df"] = grouped
        flash(f"Grouped by '{group_col}' with {agg_func} of '{agg_col}'.", "success")
    except Exception as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/text", methods=["POST"])
def format_text() -> Any:
    try:
        df = _require_dataset()
        column = request.form.get("text_column")
        action = request.form.get("text_action")
        if not column or column not in df.columns:
            raise ValueError("Choose a valid column.")
        if not action:
            raise ValueError("Choose a text formatting action.")
        _push_history(f"text {action} on '{column}'")
        updated = df.copy()
        series = updated[column].astype("string")
        if action == "strip":
            updated[column] = series.str.strip()
        elif action == "upper":
            updated[column] = series.str.upper()
        elif action == "lower":
            updated[column] = series.str.lower()
        else:
            raise ValueError("Unsupported text formatting action.")
        DATASET_STATE["df"] = updated
        flash(f"Text formatting '{action}' applied to '{column}'.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("dataset"))


@app.route("/dataset/load", methods=["POST"])
def load_to_db() -> Any:
    try:
        df = _require_dataset()
        table_name = request.form.get("table_name", "").strip()
        if not table_name:
            raise ValueError("Provide a table name.")
        df.to_sql(table_name, con=engine, if_exists="replace", index=False)
        flash(f"Saved {len(df)} rows to table '{table_name}'.", "success")
        return redirect(url_for("db_view", table=table_name))
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("dataset"))


@app.route("/db")
def db_view() -> Any:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    selected = request.args.get("table")
    preview = None
    truncated = False
    if selected and selected in tables:
        query = text(f"SELECT * FROM {selected} LIMIT {DISPLAY_LIMIT}")
        preview = pd.read_sql_query(query, engine)
        truncated = True
    return render_template(
        "db.html",
        app_title=APP_TITLE,
        tables=tables,
        selected=selected,
        preview=preview,
        truncated=truncated,
    )


if __name__ == "__main__":
    app.run(debug=True)
