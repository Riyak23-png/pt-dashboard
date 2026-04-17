"""
Google Sheets backend for the PT Dashboard.
Handles auth for both local (service account JSON) and Streamlit Cloud (secrets).
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1sjkx2-tIJ7FsOzAhMoYW191NstB24iASOtNnUBQK5WA"
SHEET_TAB = "Snapshots"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "profile_name", "date", "total_contacts", "calls",
    "emails", "web_visits", "profile_views", "results_views"
]

# Local service account JSON (used when running on laptop)
_SA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "pt_profile_creator", "pt-profile-agent-e3e19a12f782.json"
)


def _get_client():
    """Returns authenticated gspread client. Works locally and on Streamlit Cloud."""
    try:
        # Streamlit Cloud: credentials stored in st.secrets
        import streamlit as st
        info = dict(st.secrets["gcp_service_account"])
        # private_key newlines are escaped in TOML — unescape them
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        # Local: use the JSON file
        creds = Credentials.from_service_account_file(_SA_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    client = _get_client()
    return client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)


def init_sheet():
    """Ensures the Snapshots tab exists with headers. Safe to call multiple times."""
    client = _get_client()
    wb = client.open_by_key(SHEET_ID)
    try:
        ws = wb.worksheet(SHEET_TAB)
        # If headers missing (empty sheet), add them
        if not ws.row_values(1):
            ws.append_row(HEADERS)
    except gspread.WorksheetNotFound:
        ws = wb.add_worksheet(title=SHEET_TAB, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)
    return ws


def upsert_snapshot(profile_name, date, total_contacts, calls,
                    emails, web_visits, profile_views, results_views):
    """Insert or update today's snapshot for a profile."""
    ws = _get_sheet()
    all_rows = ws.get_all_values()

    row_data = [
        profile_name, date, total_contacts, calls,
        emails, web_visits, profile_views, results_views
    ]

    # Find existing row with same profile + date
    for i, row in enumerate(all_rows[1:], start=2):  # skip header
        if len(row) >= 2 and row[0] == profile_name and row[1] == date:
            ws.update(f"A{i}:H{i}", [row_data])
            return

    # Not found — append new row
    ws.append_row(row_data)


def load_dataframe():
    """Load all snapshot data as a pandas DataFrame."""
    import pandas as pd
    ws = _get_sheet()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    return df
