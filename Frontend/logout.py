import streamlit as st


def do_logout():
    # reset state
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["user_id"] = None
    st.session_state["page"] = "welcome"
    st.session_state["query"] = ""
    st.session_state["last_result"] = None
    st.session_state["busy"] = False

    st.rerun()
