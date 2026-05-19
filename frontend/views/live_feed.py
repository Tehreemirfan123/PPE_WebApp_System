"""
Live Monitor Page
─────────────────
Two modes:
  • Live Webcam  — captures from the machine running Streamlit (index 0/1/2)
  • Upload Video — user uploads an .mp4 / .avi file for offline processing

Both modes display an annotated frame stream inside the browser and build a
live violation table.  A CSV download button appears once violations exist.

The heavy ML work is done by MonitorRunner (ml_pipeline/monitor_runner.py),
which is a plain generator — no threads, no subprocesses needed.
"""

import streamlit as st
import tempfile
import sys, os
# Ensure project root is on sys.path so ml_pipeline is importable
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)
import time
from utils import api_client


# ── Lazy import so the page loads fast even if ML deps are missing ────────────
def _get_runner():
    try:
        from ml_pipeline.monitor_runner import MonitorRunner
        return MonitorRunner
    except ImportError as e:
        st.error(
            f"ML pipeline not available: {e}\n\n"
            "Make sure you are running Streamlit from the project root and "
            "all dependencies in requirements.txt are installed."
        )
        return None


# ── Session-state helpers ─────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "lm_running":       False,
        "lm_violations":    [],     # accumulated list of dicts
        "lm_frame_count":   0,
        "lm_runner":        None,
        "lm_generator":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_state():
    st.session_state["lm_running"]     = False
    st.session_state["lm_violations"]  = []
    st.session_state["lm_frame_count"] = 0
    st.session_state["lm_runner"]      = None
    st.session_state["lm_generator"]   = None


# ── Page ──────────────────────────────────────────────────────────────────────
def render():
    _init_state()

    st.markdown("## 📡 Live Monitor")
    st.markdown(
        "Run real-time PPE detection from a **webcam** or an **uploaded video file**."
    )

    # ── Mode + site selector ─────────────────────────────────────────────────
    col_mode, col_site = st.columns([1, 1])

    with col_mode:
        mode = st.radio(
            "Source",
            ["🎥 Live Webcam", "📂 Upload Video"],
            horizontal=True,
            disabled=st.session_state["lm_running"],
        )

    with col_site:
        site_options = [
            "Construction Site", "Chemical Lab", "Factory", "Warehouse"
        ]
        try:
            sites      = api_client.get_sites()
            site_names = [s["name"] for s in sites] if sites else site_options
        except Exception:
            site_names = site_options

        selected_site = st.selectbox(
            "Site",
            site_names,
            disabled=st.session_state["lm_running"],
        )

    # ── Source-specific controls ──────────────────────────────────────────────
    video_source = None

    if mode == "🎥 Live Webcam":
        cam_index = st.selectbox(
            "Webcam index",
            [0, 1, 2],
            disabled=st.session_state["lm_running"],
            help="0 = built-in / default webcam. Try 1 or 2 for USB cameras.",
        )
        video_source = cam_index

    else:  # Upload Video
        uploaded = st.file_uploader(
            "Upload a video file",
            type=["mp4", "avi", "mov", "mkv"],
            disabled=st.session_state["lm_running"],
        )
        if uploaded:
            # Save to a temp file — OpenCV needs a path, not a file object
            suffix = os.path.splitext(uploaded.name)[1]
            tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.read())
            tmp.flush()
            video_source = tmp.name
            st.success(f"✅ Loaded: **{uploaded.name}**")

    st.markdown("---")

    # ── Start / Stop controls ─────────────────────────────────────────────────
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])

    with ctrl_col1:
        start_clicked = st.button(
            "▶ Start",
            width="stretch",
            type="primary",
            disabled=st.session_state["lm_running"],
        )

    with ctrl_col2:
        stop_clicked = st.button(
            "⏹ Stop",
            width="stretch",
            disabled=not st.session_state["lm_running"],
        )

    # ── Handle Stop ──────────────────────────────────────────────────────────
    if stop_clicked:
        _reset_state()
        st.info("Monitoring stopped.")
        st.rerun()

    # ── Handle Start ─────────────────────────────────────────────────────────
    if start_clicked:
        MonitorRunner = _get_runner()
        if MonitorRunner is None:
            return

        if video_source is None:
            st.warning("⚠️ Please select or upload a video source first.")
            return

        try:
            runner = MonitorRunner(
                source         = video_source,
                site_name      = selected_site,
                log_to_backend = True,
            )
        except Exception as e:
            st.error(f"Failed to initialise models: {e}")
            return

        st.session_state["lm_runner"]    = runner
        st.session_state["lm_generator"] = runner.process()
        st.session_state["lm_running"]   = True
        st.rerun()

    # ── Display area ──────────────────────────────────────────────────────────
    st.markdown("### 🖥️ Detection Feed")

    frame_ph   = st.empty()          # video frame
    stats_ph   = st.empty()          # frame counter / violation count
    table_ph   = st.empty()          # live violations table
    csv_ph     = st.empty()          # CSV download button

    if not st.session_state["lm_running"]:
        if st.session_state["lm_violations"]:
            # Session ended — show final table + CSV
            _render_violations(table_ph, st.session_state["lm_violations"])
            _render_csv_button(
                csv_ph,
                st.session_state["lm_runner"],
                st.session_state["lm_violations"],
            )
        else:
            frame_ph.info("▶ Press **Start** to begin monitoring.")
        return

    # ── Inference loop (runs while lm_running == True) ───────────────────────
    gen = st.session_state["lm_generator"]

    try:
        frame_rgb, new_violations = next(gen)
    except StopIteration:
        st.success("✅ Video processing complete.")
        st.session_state["lm_running"] = False
        _render_violations(table_ph, st.session_state["lm_violations"])
        _render_csv_button(
            csv_ph,
            st.session_state["lm_runner"],
            st.session_state["lm_violations"],
        )
        return
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        _reset_state()
        return

    # Accumulate violations
    st.session_state["lm_violations"].extend(new_violations)
    st.session_state["lm_frame_count"] += 1

    # Render frame
    frame_ph.image(frame_rgb, channels="RGB", width="stretch")

    # Stats bar
    stats_ph.markdown(
        f"**Frame:** {st.session_state['lm_frame_count']} &nbsp;|&nbsp; "
        f"**Violations logged:** {len(st.session_state['lm_violations'])}"
    )

    # Live violations table (last 20)
    _render_violations(table_ph, st.session_state["lm_violations"])

    # CSV button appears as soon as there is data
    if st.session_state["lm_violations"]:
        _render_csv_button(
            csv_ph,
            st.session_state["lm_runner"],
            st.session_state["lm_violations"],
        )

    # Rerun to fetch next frame — Streamlit's "loop"
    time.sleep(0.01)
    st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_violations(placeholder, violations: list):
    """Render the last 20 violations as a table inside the placeholder."""
    if not violations:
        placeholder.empty()
        return

    import pandas as pd
    df = pd.DataFrame(violations[-20:])
    with placeholder.container():
        st.markdown("#### ⚠️ Violation Log (last 20)")
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_order=[
                c for c in
                ["timestamp", "site", "camera", "track_id",
                 "missing_ppe", "confidence"]
                if c in df.columns
            ],
        )


def _render_csv_button(placeholder, runner, violations: list):
    """Render a CSV download button inside the placeholder."""
    if not violations or runner is None:
        return

    csv_bytes = runner.get_csv_bytes()

    with placeholder.container():
        st.download_button(
            label     = "⬇️  Download violations as CSV",
            data      = csv_bytes,
            file_name = "ppe_violations.csv",
            mime      = "text/csv",
            width     = "content",
        )