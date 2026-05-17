"""
Streamlit Main App — Login Gate + Role-Based Navigation
"""

import streamlit as st
from utils import api_client

st.set_page_config(
    page_title="PPE Detection System",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* Metric cards */
[data-testid="stMetric"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"]  { color: #94a3b8 !important; font-size: 0.85rem; }
[data-testid="stMetricValue"]  { color: #f1f5f9 !important; font-size: 1.8rem; font-weight: 700; }
[data-testid="stMetricDelta"]  { color: #22d3ee !important; }

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

/* Login card */
.login-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2rem;
    max-width: 400px;
    margin: 0 auto;
}
.app-title { font-size: 2rem; font-weight: 700; color: #f1f5f9; margin-bottom: 0.25rem; }
.app-subtitle { color: #94a3b8; margin-bottom: 1.5rem; }

/* Status badges */
.badge-open     { background:#ef4444; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.78rem; }
.badge-resolved { background:#22c55e; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.78rem; }
.badge-default  { background:#6366f1; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.78rem; }

/* Table */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* Main bg */
.main { background: #0f172a; }
</style>

<style>
/* Make cursor pointer for all selectboxes and dropdowns */
div[data-baseweb="select"] > div,
li {
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Session state defaults ───────────────────────────────────────────────────
for key, default in [("token", None), ("role", None), ("full_name", None), ("logged_in", False)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ─── Login Page ───────────────────────────────────────────────────────────────
def show_login():
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("""
        <div class="login-card">
            <div class="app-title">🦺 PPE Monitor</div>
            <div class="app-subtitle">Safety Detection Management System</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("login_form"):
            email    = st.text_input("Email Address", placeholder="admin@ppe.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit   = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submit:
            if not email or not password:
                st.error("Please enter your email and password.")
            else:
                try:
                    resp = api_client.login(email, password)
                    st.session_state["token"]     = resp["access_token"]
                    st.session_state["role"]      = resp["role"]
                    st.session_state["full_name"] = resp["full_name"]
                    st.session_state["logged_in"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: Invalid credentials or server unavailable.")

        st.markdown("""
        <div style='color:#64748b; font-size:0.78rem; text-align:center; margin-top:1rem;'>
            Default credentials:<br>
            Admin: admin@ppe.com / admin123<br>
            Officer: officer@ppe.com / officer123
        </div>
        """, unsafe_allow_html=True)


# ─── Sidebar Navigation ───────────────────────────────────────────────────────
def show_sidebar() -> str:
    with st.sidebar:
        st.markdown(f"""
        <div style='padding:1rem 0 0.5rem'>
            <div style='font-size:1.3rem; font-weight:700;'>🦺 PPE Monitor</div>
            <div style='font-size:0.8rem; color:#64748b; margin-top:4px;'>
                {st.session_state["full_name"]}<br>
                <span style='color:#22d3ee; text-transform:uppercase; font-size:0.7rem; font-weight:600;'>
                    {st.session_state["role"].replace("_", " ")}
                </span>
            </div>
        </div>
        <hr style='border-color:#334155; margin:0.5rem 0 1rem'>
        """, unsafe_allow_html=True)

        is_admin = st.session_state["role"] == "admin"
        nav_options = ["📊 Overview", "📡 Live Monitoring", "⚠️ Violation Logs"]
        if is_admin:
            nav_options += ["🏗️ Site Management", "👷 Worker Management"]

        page = st.radio("Navigation", nav_options, label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            for key in ["token", "role", "full_name", "logged_in"]:
                st.session_state[key] = None if key != "logged_in" else False
            st.rerun()

    return page


# ─── Main router ─────────────────────────────────────────────────────────────
if not st.session_state["logged_in"]:
    # Hide the sidebar completely on the login page
    st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)
    show_login()
else:
    page = show_sidebar()

    if page == "📊 Overview":
        from views import overview
        overview.render()
    elif page == "⚠️ Violation Logs":
        from views import violations_logs
        violations_logs.render()
    elif page == "📡 Live Monitoring":
        from views import live_feed
        live_feed.render()
    elif page == "🏗️ Site Management" and st.session_state["role"] == "admin":
        from views import site_management
        site_management.render()
    elif page == "👷 Worker Management" and st.session_state["role"] == "admin":
        from views import worker_management
        worker_management.render()
    else:
        st.error("Access Denied: You do not have permission to view this page.")
