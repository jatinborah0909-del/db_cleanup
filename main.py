#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DASH DB CLEANUP PANEL – RAILWAY READY (ADVANCED)

FEATURES
--------
✔ Delete rows before a date (column selectable)
✔ Delete entire table (explicit confirmation required)
✔ Lists all user tables (public schema)
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

def delete_before_date(table_name, column_name, cutoff_date):
    with get_conn() as conn, conn.cursor() as cur:
        sql = f"""
            DELETE FROM {table_name}
            WHERE {column_name} < %s
        """
        cur.execute(sql, (cutoff_date,))
        deleted = cur.rowcount
        conn.commit()
        return deleted

def drop_table(table_name):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE {table_name}")
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
                dcc.Dropdown(
                    id="column_dd",
                    clearable=False,
                ),
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

        # ================= TABLE DELETE =================
        html.H4("🚨 Danger Zone – Delete Entire Table", className="text-danger"),

        dbc.Alert(
            "This will permanently DROP the selected table. "
            "Type the exact table name to confirm.",
            color="danger"
        ),

        dbc.Row([
            dbc.Col([
                html.Label("Confirm Table Name"),
                dbc.Input(
                    id="confirm_table_name",
                    placeholder="Type table name exactly",
                    type="text"
                ),
            ], md=6),
        ], className="mb-3"),

        dbc.Button(
            "DROP TABLE",
            id="drop_table_btn",
            color="danger",
            outline=True
        ),

        html.Div(id="table_delete_status", className="mt-3"),
    ],
    fluid=True,
)

# =========================================================
# CALLBACKS
# =========================================================

@app.callback(
    Output("column_dd", "options"),
    Output("column_dd", "value"),
    Input("table_dd", "value"),
)
def update_columns(table_name):
    if not table_name:
        return [], None

    cols = fetch_date_columns(table_name)
    return [{"label": c, "value": c} for c in cols], None


@app.callback(
    Output("row_delete_status", "children"),
    Input("delete_rows_btn", "n_clicks"),
    State("table_dd", "value"),
    State("column_dd", "value"),
    State("cutoff_date", "date"),
    prevent_initial_call=True
)
def handle_row_delete(n, table, column, cutoff):
    if not table or not column or not cutoff:
        return dbc.Alert("Select table, column and date.", color="warning")

    try:
        deleted = delete_before_date(table, column, cutoff)
        return dbc.Alert(
            f"✅ Deleted {deleted} rows from {table}",
            color="success"
        )
    except Exception as e:
        return dbc.Alert(str(e), color="danger")


@app.callback(
    Output("table_delete_status", "children"),
    Input("drop_table_btn", "n_clicks"),
    State("table_dd", "value"),
    State("confirm_table_name", "value"),
    prevent_initial_call=True
)
def handle_table_delete(n, table, confirmation):
    if not table or not confirmation:
        return dbc.Alert("Select table and confirm name.", color="warning")

    if confirmation != table:
        return dbc.Alert("❌ Table name confirmation does not match.", color="danger")

    try:
        drop_table(table)
        return dbc.Alert(
            f"🔥 Table '{table}' has been permanently deleted.",
            color="success"
        )
    except Exception as e:
        return dbc.Alert(str(e), color="danger")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8050)))
