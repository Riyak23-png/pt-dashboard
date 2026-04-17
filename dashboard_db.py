"""
Central dashboard database — stores daily snapshots for all profiles.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name     TEXT    NOT NULL,
                date             TEXT    NOT NULL,
                total_contacts   INTEGER,
                calls            INTEGER,
                emails           INTEGER,
                web_visits       INTEGER,
                profile_views    INTEGER,
                results_views    INTEGER,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_name, date)
            )
        """)
        conn.commit()


def upsert_snapshot(profile_name, date, total_contacts, calls, emails,
                    web_visits, profile_views, results_views):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO snapshots
                (profile_name, date, total_contacts, calls, emails,
                 web_visits, profile_views, results_views)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_name, date) DO UPDATE SET
                total_contacts = excluded.total_contacts,
                calls          = excluded.calls,
                emails         = excluded.emails,
                web_visits     = excluded.web_visits,
                profile_views  = excluded.profile_views,
                results_views  = excluded.results_views,
                created_at     = CURRENT_TIMESTAMP
        """, (profile_name, date, total_contacts, calls, emails,
              web_visits, profile_views, results_views))
        conn.commit()
