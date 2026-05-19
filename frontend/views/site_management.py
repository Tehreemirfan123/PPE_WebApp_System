"""
Site Management Page — Admin only
Default 4 sites are read-only. User-created sites can be edited/deleted.
"""

import streamlit as st
from utils import api_client

ALL_PPE_ITEMS = ["earmuffs", "goggles", "face_mask", "hardhat", "safety_vest",
                 "safety_shoes", "gloves", "labcoat"]

 
def render():
    st.markdown("## 🏗️ Site Management")
    st.markdown("Manage monitoring sites and their PPE requirements. Default sites are read-only.")

    # ── Current Sites ─────────────────────────────────────────────────────────
    st.markdown("### Active Sites")
    try:
        sites = api_client.get_sites()
    except Exception as e:
        st.error(f"Could not load sites: {e}")
        return

    for site in sites:
        is_default = site.get("is_default", False)
        title_suffix = " (Default)" if is_default else ""
        reqs  = [r["ppe_item"] for r in site.get("requirements", [])]

        with st.expander(f"🏗️ {site['name']}{title_suffix}", expanded=False):
            if is_default:
                st.markdown('<span class="badge-default">Default Site</span>', unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Location:** {site.get('location') or '—'}")
                st.markdown(f"**Description:** {site.get('description') or '—'}")
            with c2:
                if reqs:
                    st.markdown("**Required PPE:**")
                    st.markdown("  ".join([f"`{r}`" for r in reqs]))

            if not is_default:
                st.markdown("---")
                with st.form(f"edit_site_{site['name']}"):
                    st.markdown("**Edit Site**")
                    new_name  = st.text_input("Name",        value=site["name"])
                    new_loc   = st.text_input("Location",    value=site.get("location") or "")
                    new_desc  = st.text_area("Description",  value=site.get("description") or "", height=80)
                    new_reqs  = st.multiselect("Required PPE Items", ALL_PPE_ITEMS, default=reqs)
                    col_save, col_del = st.columns(2)
                    save_btn = col_save.form_submit_button("💾 Save Changes", width="stretch")
                    del_btn  = col_del.form_submit_button("🗑️ Delete Site",  width="stretch", type="primary")

                if save_btn:
                    try:
                        api_client.update_site(site["name"], {
                            "name": new_name, "location": new_loc,
                            "description": new_desc, "ppe_requirements": new_reqs,
                        })
                        st.success(f"Site '{new_name}' updated!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Update failed: {ex}")

                if del_btn:
                    try:
                        api_client.delete_site(site["name"])
                        st.success(f"Site '{site['name']}' deleted.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Delete failed: {ex}")

    # ── Add New Site ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ➕ Add New Site")
    with st.form("add_site_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Site Name *", placeholder="e.g. Paint Shop")
            loc  = st.text_input("Location",    placeholder="Building D, Floor 1")
        with col2:
            desc = st.text_area("Description",  placeholder="Brief description...", height=90)
            reqs = st.multiselect("Required PPE Items", ALL_PPE_ITEMS)

        submitted = st.form_submit_button("➕ Create Site", type="primary", width="stretch")

    if submitted:
        if not name.strip():
            st.error("Site name is required.")
        else:
            try:
                api_client.create_site(name.strip(), loc, desc, reqs)
                st.success(f"Site '{name}' created successfully!")
                st.rerun()
            except Exception as ex:
                st.error(f"Failed to create site: {ex}")
