import json
import requests
import streamlit as st

try:
    import pandas as pd
except Exception:
    pd = None


def _ensure_busy_state():
    st.session_state.setdefault("busy", False)
    st.session_state.setdefault("pending_action", None)
    st.session_state.setdefault("pending_error", None)
    st.session_state.setdefault("history_user_payload", None)


def _rows_from_payload(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    return []


def _normalize_json_cell(x):
    if not isinstance(x, str):
        return x
    s = x.strip()
    if not s:
        return x
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            return x
    return x


def _to_dataframe(rows):
    if pd is None:
        return None
    if len(rows) == 0:
        return pd.DataFrame([])

    # Backend history_user returns list[dict]
    if isinstance(rows[0], dict):
        df = pd.DataFrame(rows)
        for col in ("chosen_option",):
            if col in df.columns:
                df[col] = df[col].apply(_normalize_json_cell)

        # Keep only requested columns (if present)
        wanted = ["request", "dish_name",
                  "chosen_option", "explaination", "time"]
        existing = [c for c in wanted if c in df.columns]
        df = df[existing]
        rename_map = {
            "request": "request",
            "dish_name": "dish name",
            "chosen_option": "system chosen option",
            "explaination": "explanation",
            "time": "time",
        }
        df = df.rename(
            columns={k: v for k, v in rename_map.items() if k in df.columns})
        return df

    # Fallback: list[tuple] or list[list]
    rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
    max_len = max((len(r) for r in rows), default=0)
    cols = [f"col_{i}" for i in range(max_len)]
    padded = [r + [None] * (max_len - len(r)) for r in rows]
    for r in padded:
        for i, v in enumerate(r):
            r[i] = _normalize_json_cell(v)
    return pd.DataFrame(padded, columns=cols)


def render_result():
    _ensure_busy_state()
    disabled = bool(st.session_state.get("busy"))

    if not st.session_state.get("logged_in"):
        st.warning("You must log in to view History.")
        st.session_state["page"] = "login"
        st.rerun()
        return

    st.markdown(
        """
        <div style='margin-top: 0px; text-align: center; color: #fff; font-size: 40px;'>
            History Retrieval
        </div>
        """,
        unsafe_allow_html=True
    )

    # Custom CSS for table styling
    st.markdown("""
        <style>
        .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .stDataFrame > div {
            border-radius: 18px !important;
            background: rgba(30, 30, 40, 0.85) !important;
            box-shadow: 0 4px 32px 0 rgba(0,0,0,0.18);
            margin: 0 auto;
        }
        .stDataFrame th {
            background: #FFB7AB !important;
            color: #222 !important;
            font-size: 1.1em !important;
            text-align: center !important;
        }
        .stDataFrame td {
            text-align: center !important;
            font-size: 1em !important;
            color: #fff !important;
            white-space: pre-line !important;
            word-break: break-word !important;
            max-width: none !important;
        }
        .stDataFrame td, .stDataFrame th {
            max-width: none !important;
            white-space: pre-line !important;
            word-break: break-word !important;
        }
        </style>
    """, unsafe_allow_html=True)
    st.markdown("""
    <style>
    /* NỀN MỜ (glass) cho st.table */
    div[data-testid="stTable"], .stTable {
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        background: rgba(30, 30, 40, 0.35) !important;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 12px;
        box-shadow: 0 4px 32px 0 rgba(0,0,0,0.18);
        overflow: hidden; /* bo góc ăn theo table */
    }

    /* Cho cell trong bảng “trong suốt” để thấy nền mờ phía sau */
    div[data-testid="stTable"] table,
    .stTable table {
        width: 100%;
    }

    div[data-testid="stTable"] td,
    .stTable td {
        background: transparent !important;
        color: #fff !important;
        white-space: pre-line !important;
        word-break: break-word !important;
        vertical-align: top;
    }
                
    /* ĐỔI MÀU CHỮ HEADER bảng */
    div[data-testid="stTable"] thead th {
        color: #FC9249 !important;   /* Đổi sang màu cam/đỏ nổi bật */
        font-weight: bold !important;
        font-size: 1.1em !important;
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.get("pending_error"):
        st.error(st.session_state["pending_error"])
        st.session_state["pending_error"] = None

    # Execution phase for seeding one demo record (so History isn't empty)
    if st.session_state.get("pending_action") == "seed_demo":
        base_url = st.session_state["base_url"]
        user_id = st.session_state.get("user_id")
        demo_query = (st.session_state.get("query") or "").strip(
        ) or "Suggest any food/drink for demo"

        with st.spinner("Creating demo data..."):
            try:
                r = requests.post(
                    f"{base_url}/recommend",
                    json={"user_id": user_id, "query": demo_query},
                    timeout=120,
                )
                data = r.json() if r.text else None
                if r.status_code >= 400:
                    detail = data.get("detail", data) if isinstance(
                        data, dict) else data
                    raise RuntimeError(
                        detail if isinstance(detail, str) else json.dumps(
                            detail, ensure_ascii=False)
                    )

                st.session_state["history_user_payload"] = None
                st.session_state["force_reload_history"] = True
            except Exception as e:
                st.session_state["pending_error"] = f"Could not create demo data: {e}"
            finally:
                st.session_state["pending_action"] = None
                st.session_state["busy"] = False

        st.rerun()

    # Execution phase for loading merged history
    if st.session_state.get("pending_action") == "history_user":
        base_url = st.session_state["base_url"]
        user_id = st.session_state.get("user_id")

        with st.spinner("Loading history..."):
            try:
                r = requests.post(
                    f"{base_url}/history_user",
                    json={"user_id": user_id},
                    timeout=60,
                )
                data = r.json() if r.text else None
                if r.status_code >= 400:
                    detail = data.get("detail", data) if isinstance(
                        data, dict) else data
                    raise RuntimeError(
                        detail if isinstance(detail, str) else json.dumps(
                            detail, ensure_ascii=False)
                    )
                st.session_state["history_user_payload"] = data
            except Exception as e:
                st.session_state["pending_error"] = f"API call error: {e}"
                st.session_state["history_user_payload"] = None
            finally:
                st.session_state["pending_action"] = None
                st.session_state["busy"] = False

        st.rerun()

    # Auto-load history if no data or just switched to the History tab
    if (
        st.session_state.get("page") == "result"
        and (st.session_state.get("history_user_payload") is None or st.session_state.get("force_reload_history", False))
        and not st.session_state.get("busy")
        and st.session_state.get("pending_action") is None
    ):
        st.session_state["busy"] = True
        st.session_state["pending_action"] = "history_user"
        st.session_state["force_reload_history"] = False
        st.rerun()


    # Render merged history table
    payload = st.session_state.get("history_user_payload")
    if payload is not None:
        rows = _rows_from_payload(payload)
        df = _to_dataframe(rows)
        if len(rows) == 0:
            col1, col2, col3 = st.columns([1, 8, 1])
            with col2:
                st.markdown(
                    """
                    <div style='position: center; text-align: center; color: #FF736E; font-size: 25px;'>
                        ⚠️ No history records found
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        elif df is None:
            st.json(payload)
        else:
            col1, col2, col3 = st.columns([1, 8, 1])
            with col2:
                st.table(df)
