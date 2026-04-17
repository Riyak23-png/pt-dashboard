"""
PT Profile Performance Dashboard
Run with: streamlit run dashboard.py
"""

import json
import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sheets_db import load_dataframe

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

st.set_page_config(
    page_title="PT Profile Dashboard",
    page_icon="📊",
    layout="wide",
)

# Clean minimal styling
st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1a3a5c; }
    h2, h3 { color: #1a3a5c; border-bottom: 1px solid #e8eef4; padding-bottom: 6px; }
    .stMetric { background: #f4f8fc; border-radius: 10px; padding: 12px 16px; }
    .total-contacts-label {
        font-size: 13px; color: #888; font-weight: 600;
        letter-spacing: 0.04em; text-transform: uppercase;
        margin-top: 4px;
    }
    .total-contacts-row {
        display: flex; align-items: center; gap: 0;
        margin-top: -8px; margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── Load config ───────────────────────────────────────────────────────────────
with open(CONFIG_PATH) as f:
    config = json.load(f)

profiles_cfg = {p["name"]: p for p in config["profiles"]}


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    return load_dataframe()


df = load_data()

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([3, 1])
with col_title:
    st.title("Psychology Today — Profile Performance")
with col_refresh:
    st.markdown(
        f"<div style='text-align:right; color:#888; font-size:13px; margin-top:18px;'>"
        f"Updated {datetime.now().strftime('%b %d, %Y %I:%M %p')}</div>",
        unsafe_allow_html=True,
    )

# ── Alert: missing today's data ───────────────────────────────────────────────
if not df.empty:
    today_ts = pd.Timestamp(date.today())
    missing = [
        name for name in profiles_cfg
        if df[df["profile_name"] == name]["date"].max() < today_ts
    ]
    if missing:
        st.error(f"No data collected today for: **{', '.join(missing)}**. Check that the daily touch task ran.")

# ── No data state ─────────────────────────────────────────────────────────────
if df.empty:
    st.info("No data yet. Data appears automatically after the 10:00 AM daily touch.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Profile Performance Bar Chart
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## Profile Performance")
st.caption("Contacts per week, normalised by weeks live — higher is better")

summary_rows = []
for name, cfg in profiles_cfg.items():
    profile_df = df[df["profile_name"] == name]
    if profile_df.empty:
        continue
    latest = profile_df.sort_values("date").iloc[-1]
    go_live = pd.Timestamp(cfg["go_live_date"])
    weeks_live = max(1, (pd.Timestamp(date.today()) - go_live).days / 7)
    summary_rows.append({
        "Profile": name,
        "Contacts/Week": round(latest["total_contacts"] / weeks_live, 2),
        "Total Contacts": int(latest["total_contacts"]),
        "Weeks Live": round(weeks_live, 1),
        "Calls": int(latest["calls"]),
        "Emails": int(latest["emails"]),
        "Web Visits": int(latest["web_visits"]),
    })

summary_df = pd.DataFrame(summary_rows).sort_values("Contacts/Week", ascending=False)

if not summary_df.empty:
    fig_bar = px.bar(
        summary_df,
        x="Profile",
        y="Contacts/Week",
        text="Contacts/Week",
        color="Contacts/Week",
        color_continuous_scale=["#a8d0e6", "#1a5276"],
        custom_data=["Total Contacts", "Weeks Live"],
    )
    fig_bar.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        marker_line_width=0,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Contacts/Week: %{y:.2f}<br>"
            "Total Contacts: %{customdata[0]}<br>"
            "Weeks Live: %{customdata[1]}<extra></extra>"
        ),
    )
    # Build custom x-axis tick labels: Name / Total / weeks live
    tick_labels = [
        f"<b>{row['Profile']}</b><br>{row['Total Contacts']} total<br>"
        f"<span style='color:#aaa'>{row['Weeks Live']}w live</span>"
        for _, row in summary_df.iterrows()
    ]

    fig_bar.update_layout(
        xaxis_title="",
        yaxis_title="Contacts per Week",
        coloraxis_showscale=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=430,
        margin=dict(t=50, b=90, l=50, r=20),
        font=dict(family="sans-serif", size=13, color="#333"),
        xaxis=dict(
            categoryorder="total descending",
            showgrid=False,
            tickmode="array",
            tickvals=summary_df["Profile"].tolist(),
            ticktext=tick_labels,
            tickfont=dict(size=13, color="#333"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f0f0f0",
            zeroline=False,
        ),
    )

    st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — Trends
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("")
st.markdown("## Trends")
st.caption("New contacts gained per month — builds over time as daily data accumulates")

today_ts = pd.Timestamp(date.today())
three_months_ago = today_ts - timedelta(days=90)
trend_df = df[df["date"] >= three_months_ago].copy()

if not trend_df.empty:
    trend_df["month"] = trend_df["date"].dt.to_period("M")

    trend_rows = []
    for name in profiles_cfg:
        p = trend_df[trend_df["profile_name"] == name].copy()
        if p.empty:
            continue

        monthly = (
            p.sort_values("date")
            .groupby("month")["total_contacts"]
            .last()
            .reset_index()
        )
        # Diff to get contacts gained per month (not cumulative total)
        monthly["gained"] = monthly["total_contacts"].diff().clip(lower=0)
        # Drop the first row — it has no prior month to diff against
        monthly = monthly.dropna(subset=["gained"])
        monthly["gained"] = monthly["gained"].astype(int)

        has_trend = len(monthly) >= 1

        avg_per_month = round(monthly["gained"].mean(), 1) if has_trend else None
        this_month = int(monthly.iloc[-1]["gained"]) if has_trend else None
        if len(monthly) >= 2:
            delta = this_month - int(monthly.iloc[-2]["gained"])
            delta_str = f"+{delta}" if delta >= 0 else str(delta)
        else:
            delta_str = None

        trend_rows.append({
            "name": name,
            "avg_per_month": avg_per_month,
            "this_month": this_month,
            "delta_str": delta_str,
            "monthly": monthly,
            "has_trend": has_trend,
        })

    if trend_rows:
        cols = st.columns(len(trend_rows))
        for col, row in zip(cols, trend_rows):
            with col:
                st.markdown(f"**{row['name']}**")
                if not row["has_trend"]:
                    st.caption("Collecting data — trends appear after the first full month")
                else:
                    avg_str = str(row["avg_per_month"]) if row["avg_per_month"] is not None else "—"
                    this_str = str(row["this_month"]) if row["this_month"] is not None else "—"
                    vs_str = f" ({row['delta_str']} vs last)" if row["delta_str"] else ""
                    st.markdown(f"Avg/month: **{avg_str}**")
                    st.markdown(f"This month: **{this_str}**{vs_str}")

                    m = row["monthly"]
                    if len(m) >= 2:
                        fig_spark = go.Figure()
                        fig_spark.add_trace(go.Scatter(
                            x=m["month"].astype(str),
                            y=m["gained"],
                            mode="lines+markers",
                            line=dict(color="#1a6fa3", width=2),
                            marker=dict(size=7, color="#1a6fa3"),
                            fill="tozeroy",
                            fillcolor="rgba(26,111,163,0.08)",
                        ))
                        fig_spark.update_layout(
                            height=150,
                            margin=dict(l=0, r=0, t=8, b=20),
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                            xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#aaa")),
                            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickfont=dict(size=10)),
                            showlegend=False,
                        )
                        st.plotly_chart(fig_spark, use_container_width=True)
                    else:
                        st.caption("Chart appears after 2+ months of data")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Visibility Funnel
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("")
st.markdown("## Visibility Funnel")
st.caption("How people move from finding the profile to making contact")

if not summary_df.empty:
    funnel_rows = []
    for _, row in summary_df.iterrows():
        latest = df[df["profile_name"] == row["Profile"]].sort_values("date").iloc[-1]
        funnel_rows.append({
            "Profile": row["Profile"],
            "Results Views": int(latest["results_views"]),
            "Profile Views": int(latest["profile_views"]),
            "Contacts": int(latest["total_contacts"]),
        })

    funnel_df = pd.DataFrame(funnel_rows)
    funnel_melt = funnel_df.melt(
        id_vars="Profile",
        value_vars=["Results Views", "Profile Views", "Contacts"],
        var_name="Stage",
        value_name="Count",
    )

    # Stage order
    stage_order = ["Results Views", "Profile Views", "Contacts"]
    funnel_melt["Stage"] = pd.Categorical(funnel_melt["Stage"], categories=stage_order, ordered=True)

    fig_funnel = px.bar(
        funnel_melt,
        x="Profile",
        y="Count",
        color="Stage",
        barmode="group",
        text="Count",
        color_discrete_map={
            "Results Views": "#5b9fd4",
            "Profile Views": "#1f6fa3",
            "Contacts":      "#0d3b5e",
        },
        category_orders={"Stage": stage_order},
    )
    fig_funnel.update_traces(
        marker_line_width=0,
        texttemplate="%{text:,}",
        textposition="outside",
        textfont=dict(size=11, color="#444"),
    )
    fig_funnel.update_layout(
        xaxis_title="",
        yaxis_title="Count",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=420,
        font=dict(family="sans-serif", size=13, color="#333"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title="",
            font=dict(size=13),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=14, color="#333")),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False),
        margin=dict(t=60, b=40, l=50, r=20),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)
