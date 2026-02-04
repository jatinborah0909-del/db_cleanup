#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DASH DB CLEANUP PANEL – RAILWAY READY (ADVANCED + COLUMN CONTROL)

FEATURES
--------
✔ Delete rows before a date (column selectable)
✔ Delete entire table (explicit confirmation required)
✔ Add column to selected table
✔ Drop column from selected table (explicit confirmation required)
✔ Lists all user tables & columns (public schema)
✔ Safe, Railway compatible
"""

import os
import psycopg2
from datetime import date

import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

# =========================================================
# CONFIG
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env var not found")

# =========================================================
# DB HELPERS
# =========================================================

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def fetch_tables():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        return [r[0] for r in cur.fetchall()]

def fetch_date_columns(table_name):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND data_type IN (
                  'date',
                  'timestamp without time zone',
                  'timestamp with time zone'
              )
            ORDER BY column_name
        """, (table_name,))
        return [r[0] for r in cur.fetchall()]

def fetch_all_columns(table_name):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY column_name
        """, (table_name,))
        return [r[0] for r in cur.fetchall()]

def delete_before_date(table_name, column_name, cutoff_date):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {table_name} WHERE {column_name} < %s",
            (cutoff_date,)
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted

def drop_table(table_name):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE {table_name}")
        conn.commit()

def add_column(table_name, column_name, data_type):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}"
        )
        conn.commit()

def drop_column(table_name, column_name):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        )
        conn.commit()

# =========================================================
# DASH APP
# =========================================================

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

tables = fetch_tables()

app.layout = dbc.Container(
    [
        html.H2("Database Cleanup Utility 🧹", className="mt-4"),
        html.Hr(),

        # ================= ROW DELETE =================
        dbc.Alert(
            "⚠️ Delete rows BEFORE a date using a selected column.",
            color="warning"
        ),

        dbc.Row([
            dbc.Col([
                html.Label("Select Table"),
                dcc.Dropdown(
                    id="table_dd",
                    options=[{"label": t, "value": t} for t in tables],
                    clearable=False,
                ),
            ], md=4),

            dbc.Col([
                html.Label("Select Date Column"),
                dcc.Dropdown(id="date_column_dd", clearable=False),
            ], md=4),

            dbc.Col([
                html.Label("Delete rows BEFORE date"),
                dcc.DatePickerSingle(
                    id="cutoff_date",
                    max_date_allowed=date.today(),
                    display_format="YYYY-MM-DD",
                ),
            ], md=4),
        ], className="mb-3"),

        dbc.Button("DELETE ROWS", id="delete_rows_btn", color="danger"),
        html.Div(id="row_delete_status", className="mt-3"),

        html.Hr(className="my-4"),

        # ================= COLUMN MANAGEMENT =================
        html.H4("🧩 Column Management"),

        dbc.Row([
            dbc.Col([
                html.Label("Existing Columns"),
                dcc.Dropdown(id="all_columns_dd"),
            ], md=4),

            dbc.Col([
                html.Label("Confirm Column Name (for DROP)"),
                dbc.Input(id="confirm_column_name", type="text"),
            ], md=4),

            dbc.Col([
                dbc.Button(
                    "DROP COLUMN",
                    id="drop_column_btn",
                    color="danger",
                    outline=True,
                    className="mt-4"
                ),
            ], md=4),
        ]),

        html.Div(id="drop_column_status", className="mt-2"),

        html.Hr(),

        dbc.Row([
            dbc.Col([
                html.Label("New Column Name"),
                dbc.Input(id="new_column_name", type="text"),
            ], md=4),

            dbc.Col([
                html.Label("Data Type"),
                dcc.Dropdown(
                    id="new_column_type",
                    options=[
                        {"label": "TEXT", "value": "TEXT"},
                        {"label": "INTEGER", "value": "INTEGER"},
                        {"label": "NUMERIC", "value": "NUMERIC"},
                        {"label": "BOOLEAN", "value": "BOOLEAN"},
                        {"label": "DATE", "value": "DATE"},
                        {"label": "TIMESTAMP", "value": "TIMESTAMP"},
                    ],
                    clearable=False,
                ),
            ], md=4),

            dbc.Col([
                dbc.Button(
                    "ADD COLUMN",
                    id="add_column_btn",
                    color="success",
                    className="mt-4"
                ),
            ], md=4),
        ]),

        html.Div(id="add_column_status", className="mt-2"),

        html.Hr(className="my-4"),

        # ================= TABLE DELETE =================
        html.H4("🚨 Danger Zone – Delete Entire Table", className="text-danger"),

        dbc.Alert(
            "This will permanently DROP the selected table. "
            "Type the exact table name to confirm.",
            color="danger"
        ),

        dbc.Input(
            id="confirm_table_name",
            placeholder="Type table name exactly",
            type="text"
        ),

        dbc.Button(
            "DROP TABLE",
            id="drop_table_btn",
            color="danger",
            outline=True,
            className="mt-2"
        ),

        html.Div(id="table_delete_status", className="mt-3"),
    ],
    fluid=True,
)

# =========================================================
# CALLBACKS
# =========================================================

@app.callback(
    Output("date_column_dd", "options"),
    Output("date_column_dd", "value"),
    Output("all_columns_dd", "options"),
    Output("all_columns_dd", "value"),
    Input("table_dd", "value"),
)
def update_columns(table):
    if not table:
        return [], None, [], None

    date_cols = fetch_date_columns(table)
    all_cols = fetch_all_columns(table)

    return (
        [{"label": c, "value": c} for c in date_cols],
        None,
        [{"label": c, "value": c} for c in all_cols],
        None
    )

@app.callback(
    Output("row_delete_status", "children"),
    Input("delete_rows_btn", "n_clicks"),
    State("table_dd", "value"),
    State("date_column_dd", "value"),
    State("cutoff_date", "date"),
    prevent_initial_call=True
)
def handle_row_delete(_, table, column, cutoff):
    if not table or not column or not cutoff:
        return dbc.Alert("Select table, column and date.", color="warning")

    deleted = delete_before_date(table, column, cutoff)
    return dbc.Alert(f"✅ Deleted {deleted} rows from {table}", color="success")

@app.callback(
    Output("add_column_status", "children"),
    Input("add_column_btn", "n_clicks"),
    State("table_dd", "value"),
    State("new_column_name", "value"),
    State("new_column_type", "value"),
    prevent_initial_call=True
)
def handle_add_column(_, table, col, dtype):
    if not table or not col or not dtype:
        return dbc.Alert("Provide table, column name and type.", color="warning")

    try:
        add_column(table, col, dtype)
        return dbc.Alert(f"✅ Column '{col}' added to {table}", color="success")
    except Exception as e:
        return dbc.Alert(str(e), color="danger")

@app.callback(
    Output("drop_column_status", "children"),
    Input("drop_column_btn", "n_clicks"),
    State("table_dd", "value"),
    State("all_columns_dd", "value"),
    State("confirm_column_name", "value"),
    prevent_initial_call=True
)
def handle_drop_column(_, table, col, confirm):
    if not table or not col or not confirm:
        return dbc.Alert("Select column and confirm name.", color="warning")

    if col != confirm:
        return dbc.Alert("❌ Column name confirmation mismatch.", color="danger")

    try:
        drop_column(table, col)
        return dbc.Alert(f"🔥 Column '{col}' dropped from {table}", color="success")
    except Exception as e:
        return dbc.Alert(str(e), color="danger")

@app.callback(
    Output("table_delete_status", "children"),
    Input("drop_table_btn", "n_clicks"),
    State("table_dd", "value"),
    State("confirm_table_name", "value"),
    prevent_initial_call=True
)
def handle_table_delete(_, table, confirmation):
    if not table or confirmation != table:
        return dbc.Alert("❌ Table name confirmation mismatch.", color="danger")

    drop_table(table)
    return dbc.Alert(f"🔥 Table '{table}' deleted.", color="success")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8050)))
