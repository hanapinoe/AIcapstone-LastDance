import json
import requests
import streamlit as st


def _ensure_busy_state():
    st.session_state.setdefault("busy", False)
    st.session_state.setdefault("pending_action", None)
    st.session_state.setdefault("pending_error", None)


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

    # If we are in the "execution phase"
    if st.session_state.get("pending_action") == "recommend":
        base_url = st.session_state["base_url"]
        user = st.session_state.get("user")
        query = (st.session_state.get("query") or "").strip()

        if not query:
            st.session_state["pending_action"] = None
            st.session_state["busy"] = False
            st.session_state["pending_error"] = "You must enter a query!"
            st.rerun()

        user_id = st.session_state.get("user_id")
        payload = {"user_id": user_id, "query": query} if user_id is not None else {
            "user": user, "query": query}

        with st.spinner("Processing, please wait..."):
            try:
                r = requests.post(f"{base_url}/recommend",
                                  json=payload, timeout=300)
                data = r.json() if r.text else None

                if r.status_code >= 400:
                    detail = data.get("detail", data) if isinstance(
                        data, dict) else data
                    raise Exception(detail if isinstance(
                        detail, str) else json.dumps(detail, ensure_ascii=False))

                st.session_state["last_result"] = data
                # Mark History as stale so it reloads and shows the new record
                st.session_state["history_user_payload"] = None
                st.session_state["force_reload_history"] = True
            except Exception as e:
                st.session_state["pending_error"] = f"API call error: {e}"
            finally:
                st.session_state["pending_action"] = None
                st.session_state["busy"] = False

        st.rerun()

    # Input phase
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Recommend", use_container_width=True, disabled=disabled):
            query = (st.session_state.get("query") or "").strip()
            if not query:
                st.error("You must enter a query!")
                return

            st.session_state["busy"] = True
            st.session_state["pending_action"] = "recommend"
            st.rerun()

    # Show latest result as a table (stay on Query page)
    if st.session_state.get("last_result") is not None:
        st.divider()
        st.subheader("Result")
        result = st.session_state.get("last_result")

        recommended_options = {}
        if isinstance(result, dict):
            recommended_options = result.get("recommended_options") or {}

        if isinstance(recommended_options, dict) and len(recommended_options) > 0:
            try:
                import pandas as pd

                df = pd.DataFrame([{"key": k, "value": v}
                                  for k, v in recommended_options.items()])
                # hoặc [" ", " "] để tránh một số renderer
                df.columns = ["", ""]
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception:
                st.json(recommended_options)
        else:
            st.info("No recommended options to display.")

        for k, v in recommended_options.items():
            st.markdown(
                f"<div style='padding:4px 0;'><b>{k}:</b> {v}</div>", unsafe_allow_html=True)
