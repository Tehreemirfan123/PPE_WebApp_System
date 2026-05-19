"""
Worker Management Page — Admin only
Add, update, remove workers and upload face photos.
"""

import streamlit as st
from utils import api_client


def render():
    st.markdown("## 👷 Worker Management")
    st.markdown("Register and manage site workers. Upload face photos for recognition by the ML pipeline.")

    # ── Worker List ───────────────────────────────────────────────────────────
    st.markdown("### Registered Workers")
    try:
        workers = api_client.get_workers()
        sites   = api_client.get_sites()
        site_names = [s["name"] for s in sites]
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    if not workers:
        st.info("No workers registered yet.")
    else:
        for w in workers:
            site_name = w.get("site_name") or "Unassigned"
            has_face  = bool(w.get("face_image_path"))

            with st.expander(f"👷 {w['full_name']}  —  {w['employee_id']}", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Employee ID:** {w['employee_id']}")
                    st.markdown(f"**Department:** {w.get('department') or '—'}")
                    st.markdown(f"**Site:** {site_name}")
                    st.markdown(f"**Face Photo:** {'✅ Uploaded' if has_face else '❌ Not uploaded'}")
                    st.markdown(f"**Status:** {'Active' if w['is_active'] else 'Inactive'}")

                with c2:
                    # Upload face photo
                    st.markdown("**Upload / Update Face Photo**")
                    uploaded = st.file_uploader(
                        "Face photo (JPG/PNG)", type=["jpg", "jpeg", "png"],
                        key=f"face_{w['employee_id']}",
                    )
                    if uploaded and st.button("📤 Upload Face", key=f"up_face_{w['employee_id']}"):
                        try:
                            api_client.upload_face(w["employee_id"], uploaded.read(), uploaded.name)
                            st.success("Face photo uploaded! ML pipeline will generate embedding.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Upload failed: {ex}")

                st.markdown("---")
                # Edit form
                with st.form(f"edit_worker_{w['employee_id']}"):
                    st.markdown("**Edit Worker Info**")
                    new_name  = st.text_input("Full Name",   value=w["full_name"])
                    new_dept  = st.text_input("Department",  value=w.get("department") or "")
                    site_opts = ["Unassigned"] + site_names
                    cur_site  = w.get("site_name") or "Unassigned"
                    new_site  = st.selectbox("Site", site_opts, index=site_opts.index(cur_site) if cur_site in site_opts else 0)
                    new_active = st.checkbox("Active", value=w["is_active"])
                    col_save, col_del = st.columns(2)
                    save_btn = col_save.form_submit_button("💾 Save", width="stretch")
                    del_btn  = col_del.form_submit_button("🗑️ Remove Worker", width="stretch", type="primary")

                if save_btn:
                    try:
                        api_client.update_worker(w["employee_id"], {
                            "full_name":  new_name,
                            "department": new_dept,
                            "site_name":  new_site if new_site != "Unassigned" else None,
                            "is_active":  new_active,
                        })
                        st.success("Worker updated!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Update failed: {ex}")

                if del_btn:
                    try:
                        api_client.delete_worker(w["employee_id"])
                        st.success("Worker removed.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Delete failed: {ex}")

    # ── Add New Worker ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ➕ Register New Worker")
    with st.form("add_worker_form", clear_on_submit=True):
        co1, co2 = st.columns(2)
        with co1:
            emp_id   = st.text_input("Employee ID *",  placeholder="EMP-001")
            name     = st.text_input("Full Name *",    placeholder="Ali Hassan")
        with co2:
            dept     = st.text_input("Department",     placeholder="Engineering")
            site_opts = ["Unassigned"] + site_names
            sel_site = st.selectbox("Assigned Site", site_opts)

        submitted = st.form_submit_button("➕ Register Worker", type="primary", width="stretch")

    if submitted:
        if not emp_id.strip() or not name.strip():
            st.error("Employee ID and Full Name are required.")
        else:
            try:
                resp = api_client.create_worker(
                    employee_id=emp_id.strip(),
                    full_name=name.strip(),
                    department=dept or None,
                    site_name=sel_site if sel_site != "Unassigned" else None,
                )
                st.success(f"Worker '{name}' registered! Upload a face photo to enable recognition.")
                st.rerun()
            except Exception as ex:
                st.error(f"Registration failed: {ex}")
