"""
Overview Page — Stats cards + bar chart by site + compliance gauge
"""

import sys
import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# Fix import paths
_frontend_dir = os.path.dirname(os.path.abspath(__file__))
_frontend_parent = os.path.dirname(_frontend_dir)
if _frontend_parent not in sys.path:
    sys.path.insert(0, _frontend_parent)

from utils import api_client


def render():
    st.markdown("## 📊 Overview Dashboard")
    st.markdown("Real-time PPE violation statistics across all monitored sites.")

    try:
        stats = api_client.get_dashboard_stats()
    except Exception as e:
        st.error(f"Failed to load stats: {e}")
        return

    # ── Metric Cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🚨 Total Violations",  stats["total_violations"])
    with c2:
        st.metric("📅 Today's Violations", stats["violations_today"])
    with c3:
        st.metric("🔴 Open",              stats["open_violations"])
    with c4:
        st.metric("✅ Resolved",          stats["resolved_violations"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts Row ────────────────────────────────────────────────────────────
    col_bar, col_gauge = st.columns([2, 1])

    with col_bar:
        st.markdown("#### Violations by Site")
        sites  = [row["site"]  for row in stats["by_site"]]
        counts = [row["count"] for row in stats["by_site"]]
        colors = ["#ef4444", "#f97316", "#eab308", "#22c55e"]

        fig_bar = go.Figure(go.Bar(
            x=sites, y=counts,
            marker_color=colors[:len(sites)],
            text=counts, textposition="outside",
        ))
        fig_bar.update_layout(
            plot_bgcolor="#1e293b", paper_bgcolor="#1e293b",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="#334155"),
            yaxis=dict(gridcolor="#334155"),
            margin=dict(t=20, b=20, l=20, r=20),
            height=320,
        )
        st.plotly_chart(fig_bar, width="stretch")

    with col_gauge:
        st.markdown("#### Compliance Rate")
        rate = stats["compliance_rate"] * 100
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=rate,
            number={"suffix": "%", "font": {"color": "#f1f5f9", "size": 36}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#64748b"},
                "bar":  {"color": "#22c55e" if rate >= 70 else "#ef4444"},
                "bgcolor": "#1e293b",
                "steps": [
                    {"range": [0, 50],  "color": "#450a0a"},
                    {"range": [50, 70], "color": "#431407"},
                    {"range": [70, 100],"color": "#052e16"},
                ],
                "threshold": {"line": {"color": "#22d3ee", "width": 3}, "value": 80},
            },
        ))
        fig_gauge.update_layout(
            paper_bgcolor="#1e293b", font=dict(color="#e2e8f0"),
            margin=dict(t=20, b=20, l=30, r=30), height=320,
        )
        st.plotly_chart(fig_gauge, width="stretch")

    # ── Site Breakdown Table ──────────────────────────────────────────────────
    if stats["by_site"]:
        st.markdown("#### Site Breakdown")
        import pandas as pd
        df = pd.DataFrame(stats["by_site"])
        df.columns = ["Site", "Violations"]
        df["Share"] = (df["Violations"] / df["Violations"].sum() * 100).round(1).astype(str) + "%"
        st.dataframe(df, width="stretch", hide_index=True)
