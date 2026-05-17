"""
Live Violations Page — Multi-camera grid + real-time alerts
"""

import streamlit as st
import time
from utils import api_client


def render():
    st.markdown("## 📡 Live Monitoring")
    st.markdown("Real-time video streams with PPE detection overlays")

    # ─────────────────────────────────────────────────────────────
    # Load Cameras
    # ─────────────────────────────────────────────────────────────
    try:
        cameras = api_client.get_cameras()
    except Exception as e:
        st.error(f"Failed to load cameras: {e}")
        return

    if not cameras:
        st.warning("⚠️ No cameras available.")
        return

    # ─────────────────────────────────────────────────────────────
    # Stream Controls
    # ─────────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 1])

    with col1:
        start_stream = st.button("▶️ Start Live Monitoring", use_container_width=True)

    with col2:
        stop_stream = st.button("⏹️ Stop", use_container_width=True)

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────
    # Layout: Grid + Alerts Panel
    # ─────────────────────────────────────────────────────────────
    left_col, right_col = st.columns([3, 1])

    # ─────────────────────────────────────────────────────────────
    # LEFT: Camera Grid
    # ─────────────────────────────────────────────────────────────
    with left_col:
        st.markdown("### 🎥 Live Camera Feeds")

        # Create grid (2 cameras per row)
        grid_cols = st.columns(2)

        placeholders = []

        for i, cam in enumerate(cameras):
            with grid_cols[i % 2]:
                st.markdown(f"**{cam['camera_name']}**")
                ph = st.empty()
                placeholders.append((ph, cam["id"]))

    # ─────────────────────────────────────────────────────────────
    # RIGHT: Alerts Panel
    # ─────────────────────────────────────────────────────────────
    with right_col:
        st.markdown("### 🚨 Live Alerts")
        alerts_placeholder = st.empty()

    # ─────────────────────────────────────────────────────────────
    # Streaming Loop
    # ─────────────────────────────────────────────────────────────
    if start_stream:
        st.success("Live monitoring started...")

        while True:
            try:
                # ── Update Camera Feeds ──
                for ph, cam_id in placeholders:
                    stream_url = api_client.get_stream_url(cam_id)

                    # Display stream
                    ph.image(
                        stream_url,
                        use_column_width=True,
                        caption=f"Camera {cam_id}"
                    )

                # ── Fetch Latest Violations ──
                try:
                    latest_violations = api_client.get_violations(status="open")
                except:
                    latest_violations = []

                # ── Display Alerts ──
                with alerts_placeholder.container():
                    if not latest_violations:
                        st.success("✅ No active violations")
                    else:
                        for v in latest_violations[:5]:  # show top 5
                            worker = v.get("worker_name") or "Unknown"
                            item = v.get("missing_item")
                            site = v.get("site_name")
                            ts = v["timestamp"][:19].replace("T", " ")

                            st.error(
                                f"🚨 {worker} missing **{item}**\n"
                                f"📍 {site}\n"
                                f"🕐 {ts}"
                            )

                # Delay (controls refresh rate)
                time.sleep(1)

                # Stop condition
                if stop_stream:
                    st.warning("Monitoring stopped.")
                    break

            except Exception as e:
                st.error(f"Streaming error: {e}")
                break

    else:
        st.info("Click 'Start Live Monitoring' to begin.")