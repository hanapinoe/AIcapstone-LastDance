import streamlit as st


def do_logout():
    # clear persisted auth (query params)
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

    # reset state
    st.session_state["logged_in"] = False
    st.session_state["user"] = {}
    st.session_state["user_id"] = None
    st.session_state["page"] = "welcome"
    st.session_state["query"] = ""
    st.session_state["last_result"] = None
    st.session_state["busy"] = False

    st.rerun()
