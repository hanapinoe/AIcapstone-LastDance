import json
import requests
import streamlit as st
import concurrent.futures
import time


_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# How often to poll a running background recommend() call.
_RECOMMEND_POLL_INTERVAL_SEC = 0.5


def _white_notice(text: str):
    # Simple white “toast-like” box (avoid Streamlit st.info blue).
    safe = (text or "").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
        <div style='background:#fff; color:#222; padding:12px 16px; border-radius:8px; border:1px solid #eee; text-align:center;'>
            <b>{safe}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_busy_state():
    st.session_state.setdefault("busy", False)
    st.session_state.setdefault("pending_action", None)
    st.session_state.setdefault("pending_error", None)
    st.session_state.setdefault("recommend_future", None)
    st.session_state.setdefault("recommend_cancelled", False)


def _call_recommend(base_url: str, payload: dict):
    r = requests.post(f"{base_url}/recommend", json=payload, timeout=300)
    data = r.json() if r.text else None
    if r.status_code >= 400:
        detail = data.get("detail", data) if isinstance(data, dict) else data
        raise Exception(detail if isinstance(detail, str)
                        else json.dumps(detail, ensure_ascii=False))
    return data


def render_query():
    if not st.session_state.get("logged_in"):
        st.warning("You must log in to use this feature.")
        st.session_state["page"] = "login"
        st.rerun()
        return

    _ensure_busy_state()
    disabled = bool(st.session_state.get("busy"))

    st.markdown(
        """
        <div style='margin-top: 0px; text-align: center; color: #fff; font-size: 40px;'>
            What would you like to eat today?
        </div>
        """,
        unsafe_allow_html=True
    )

    # Styling for result table: blur/glass background, bigger fonts, and wrapped long text.
    st.markdown(
        """
        <style>
        div[data-testid="stTable"], .stTable {
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            background: rgba(30, 30, 40, 0.35) !important;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 14px;
            padding: 10px;
            box-shadow: 0 4px 32px 0 rgba(0,0,0,0.18);
            overflow: hidden;
        }

        div[data-testid="stTable"] table, .stTable table {
            width: 100%;
        }

        div[data-testid="stTable"] thead th, .stTable thead th {
            color: #fff !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
            text-align: left !important;
            background: transparent !important;
        }

        div[data-testid="stTable"] td, .stTable td {
            background: transparent !important;
            color: #fff !important;
            font-size: 1.05rem !important;
            white-space: pre-wrap !important;
            word-break: break-word !important;
            overflow-wrap: anywhere !important;
            vertical-align: top;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Show any pending error from last action
    if st.session_state.get("pending_error"):
        st.error(st.session_state["pending_error"])
        st.session_state["pending_error"] = None

    st.session_state["query"] = st.text_area(
        "",
        height=140,
        value=st.session_state.get("query", ""),
        placeholder="Input your query here...",
        disabled=disabled,
    )

    # --- if a recommend request is running in background ---
    future = st.session_state.get("recommend_future")
    if future is not None:
        if future.done():
            try:
                data = future.result()
                # nếu user đã bấm Stop thì bỏ kết quả
                if not st.session_state.get("recommend_cancelled"):
                    st.session_state["last_result"] = data
                    st.session_state["history_user_payload"] = None
                    st.session_state["force_reload_history"] = True
            except Exception as e:
                if not st.session_state.get("recommend_cancelled"):
                    st.session_state["pending_error"] = f"API call error: {e}"
            finally:
                st.session_state["recommend_future"] = None
                st.session_state["recommend_cancelled"] = False
                st.session_state["busy"] = False
                st.session_state["pending_action"] = None
            st.rerun()
        else:
            _white_notice("Processing, please wait...")
            # cho Stop bấm được trong lúc đang chạy
            if st.button("Stop", use_container_width=True, disabled=False):
                base_url = st.session_state["base_url"]
                st.session_state["recommend_cancelled"] = True
                try:
                    requests.post(f"{base_url}/stop", timeout=2)
                except Exception:
                    pass
                # không cancel được thread đang chạy thật sự, nhưng ta “bỏ qua” kết quả
                # IMPORTANT: clear future so UI stops showing “Processing”.
                st.session_state["recommend_future"] = None
                st.session_state["busy"] = False
                st.session_state["pending_action"] = None
                st.rerun()

            # IMPORTANT: Streamlit does not rerun automatically when a background
            # Future completes. Poll + rerun so the UI updates right after 200 OK.
            time.sleep(_RECOMMEND_POLL_INTERVAL_SEC)
            st.rerun()
            return

    # Legacy flag compatibility: never run recommend synchronously.
    # If some other page accidentally sets pending_action="recommend", just clear it.
    if st.session_state.get("pending_action") == "recommend":
        st.session_state["pending_action"] = None
        st.rerun()

    # Input phase
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Recommend", use_container_width=True, disabled=disabled):
            base_url = st.session_state["base_url"]
            user = st.session_state.get("user")
            query = (st.session_state.get("query") or "").strip()
            if not query:
                st.error("You must enter a query!")
                return

            user_id = st.session_state.get("user_id")
            payload = {"user_id": user_id, "query": query} if user_id is not None else {
                "user": user, "query": query}

            # resume backend nếu trước đó đã stop
            try:
                requests.post(f"{base_url}/resume", timeout=2)
            except Exception:
                pass

            st.session_state["busy"] = True
            st.session_state["recommend_cancelled"] = False
            st.session_state["recommend_future"] = _EXECUTOR.submit(
                _call_recommend, base_url, payload)
            st.rerun()

    with col2:
        # Keep Stop clickable; actual running-state Stop is handled above.
        if st.button("Stop", use_container_width=True, disabled=False):
            base_url = st.session_state["base_url"]
            try:
                requests.post(f"{base_url}/stop", timeout=2)
            except Exception:
                pass
            st.session_state["busy"] = False
            st.session_state["pending_action"] = None
            st.rerun()

    # Show latest result as a table (stay on Query page)
    if st.session_state.get("last_result") is not None:
        st.divider()
        st.subheader("Result")
        result = st.session_state.get("last_result")

        chosen = None
        reason = None
        if isinstance(result, dict):
            chosen = result.get("chosen")
            reason = (
                result.get("reason")
                or result.get("explaination")
                or result.get("explanation")
            )

        if isinstance(chosen, dict) and (chosen.get("name") or chosen.get("type")):
            name = chosen.get("name")
            dish_type = chosen.get("type")
            score = chosen.get("score")
            parts = []
            if name:
                parts.append(f"<b>Chosen:</b> {name}")
            if dish_type:
                parts.append(f"<b>Type:</b> {dish_type}")
            if score is not None:
                parts.append(f"<b>Score:</b> {score}")
            st.markdown(
                """
                <div style='backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); background: rgba(30, 30, 40, 0.35); border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 10px 12px; color: #fff; font-size: 1.05rem; margin: 6px 0 12px 0;'>
                    {content}
                </div>
                """.format(content=" &nbsp; | &nbsp; ".join(parts)),
                unsafe_allow_html=True,
            )

        recommended_options = None
        if isinstance(result, dict):
            recommended_options = result.get("recommended_options")

        if isinstance(recommended_options, dict) and len(recommended_options) > 0:
            rows = [{"Option": k, "Value": v}
                    for k, v in recommended_options.items()]
            try:
                import pandas as pd

                st.table(pd.DataFrame(rows))
            except Exception:
                st.table(rows)
        elif isinstance(recommended_options, list) and len(recommended_options) > 0:
            # If backend returns a list of rows (e.g. list[dict]), show it directly.
            st.table(recommended_options)
        else:
            _white_notice("No recommended options to display.")

        if isinstance(reason, str) and reason.strip():
            st.markdown(
                """
                <div style='backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); background: rgba(30, 30, 40, 0.35); border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 10px 12px; color: #fff; font-size: 1.05rem; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;'>
                    <b>Explanation:</b><br/>{reason}
                </div>
                """.format(reason=(reason or "").replace("<", "&lt;").replace(">", "&gt;")),
                unsafe_allow_html=True,
            )
