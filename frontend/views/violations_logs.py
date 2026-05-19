"""
Violations Logs Page — Filterable table + image viewer + resolve button
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from utils import api_client
import requests
import base64

def handle_resolve_violation(violation_id):
    """Callback function to handle API resolution logic before page re-rendering."""
    import requests  # Imported to catch the explicit HTTP error signature
    
    try:
        from utils import api_client
        api_client.resolve_violation(violation_id)
        st.session_state[f"msg_success_{violation_id}"] = f"Violation #{violation_id} marked as resolved!"
    
    except requests.exceptions.HTTPError as http_err:
        # Check if the backend responded with a 403 Forbidden status code
        if http_err.response is not None and http_err.response.status_code == 403:
            st.session_state[f"msg_error_{violation_id}"] = "🚫 Action Denied: Violations can only be resolved by a Security Officer."
        else:
            st.session_state[f"msg_error_{violation_id}"] = f"Server Error: {http_err}"
            
    except Exception as ex:
        st.session_state[f"msg_error_{violation_id}"] = f"Failed to resolve: {ex}"

def render():
    st.markdown("## ⚠️Violations Logs")
    st.markdown("Browse detected PPE violations")

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)

        # Populate site options
        try:
            sites = api_client.get_sites()
            site_names = [s["name"] for s in sites]
        except:
            site_names = []

        with f1:
            sel_site   = st.selectbox("Site", ["All"] + site_names)
        with f2:
            sel_status = st.selectbox("Status", ["All", "open", "resolved"])
        with f3:
            date_from = st.date_input("From", value=date.today() - timedelta(days=30))
        with f4:
            date_to   = st.date_input("To",   value=date.today())
        with f5:
            st.markdown("<br>", unsafe_allow_html=True)
            refresh_btn = st.button("🔄 Refresh", width="stretch")

    site_name = sel_site if sel_site != "All" else None
    status    = sel_status if sel_status != "All" else None

    # ── Fetch Violations ──────────────────────────────────────────────────────
    try:
        violations = api_client.get_violations(
            site_name=site_name, status=status,
            date_from=date_from, date_to=date_to,
        )
    except Exception as e:
        st.error(f"Failed to load violations: {e}")
        return

    if not violations:
        st.info("✅ No violations found for the selected filters.")
        return

    st.markdown(f"**{len(violations)} violation(s) found**")
    st.markdown("---")

    # ── Violation Cards ───────────────────────────────────────────────────────
    for v in violations:
        status_badge = (
            '<span class="badge-open">Open</span>'
            if v["status"] == "open"
            else '<span class="badge-resolved">Resolved</span>'
        )
        site_name   = v.get("site_name")   or "—"
        cam_name    = v.get("camera_name") or "—"
        worker_name = v.get("worker_name") or "Unknown Worker"
        ts          = v["timestamp"][:19].replace("T", " ")

        with st.container():
            img_col, info_col = st.columns([1, 2])

            with img_col:
                img_path = v.get("image_path")
                if img_path:
                    if img_path.startswith("data:image"):
                        image_bytes = base64.b64decode(img_path.split(",", 1)[1])
                        st.image(image_bytes, width="stretch", caption="Violation Frame")
                    else:
                        # Backward-compatible path for older records that only stored a filename.
                        filename = img_path.split("/")[-1].split("\\")[-1]
                        img_url  = f"{api_client.BASE_URL}/images/{filename}"
                        try:
                            resp = requests.get(img_url, timeout=5)
                            if resp.status_code == 200:
                                st.image(resp.content, width="stretch", caption="Violation Frame")
                            else:
                                st.image("https://via.placeholder.com/300x200?text=No+Image", width="stretch")
                        except:
                            st.image("https://via.placeholder.com/300x200?text=No+Image", width="stretch")
                else:
                    st.markdown("""
                    <div style='height:150px;background:#334155;border-radius:8px;
                                display:flex;align-items:center;justify-content:center;
                                color:#64748b;font-size:0.85rem;'>
                        No image saved
                    </div>
                    """, unsafe_allow_html=True)

            with info_col:
                st.markdown(f"""
                **Violation #{v['id']}** &nbsp; {status_badge}

                | Field | Value |
                |---|---|
                | 🔴 Missing PPE | `{v['missing_item']}` |
                | 👷 Worker | {worker_name} |
                | 🏗️ Site | {site_name} |
                | 📷 Camera | {cam_name} |
                | 🕐 Timestamp | {ts} |
                | 📊 Confidence | {f"{v['confidence_score']:.2%}" if v.get('confidence_score') else '—'} |
                """, unsafe_allow_html=True)

                if v["status"] == "open":
                    # Proactively check if the user has the authority to run this action
                    if st.session_state.get("role") == "security_officer":
                        st.button(
                            f"✅ Mark Resolved", 
                            key=f"resolve_{v['id']}",
                            on_click=handle_resolve_violation,
                            args=(v["id"],)
                        )
                    else:
                        # Display a clean, locked indicator instead of a button they can't use
                        st.markdown("🔒 *Only Security Officers can resolve violations*")

                    # Display status notifications safely above or below the record card
                    if f"msg_success_{v['id']}" in st.session_state:
                        st.success(st.session_state.pop(f"msg_success_{v['id']}"))
                    if f"msg_error_{v['id']}" in st.session_state:
                        st.error(st.session_state.pop(f"msg_error_{v['id']}"))
                else:
                    resolved_at = v.get("resolved_at", "")
                    if resolved_at:
                        resolved_at = resolved_at[:19].replace("T", " ")
                    st.success(f"Resolved at {resolved_at}")

        st.markdown("---")
