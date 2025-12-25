import json
import requests
import streamlit as st


def render_login():
    st.markdown("""
        <style>
        .auth-box{
            max-width: 420px;          /* CHỈNH SIZE Ở ĐÂY */
            margin: 30px auto 0 auto;  /* khoảng cách phía trên */
            padding: 26px 22px;
            background: rgba(30, 30, 40, 0.70);
            border-radius: 18px;
            box-shadow: 0 4px 32px rgba(0,0,0,0.18);
        }
        .auth-title{
            text-align:center;
            font-size: 28px;
            font-weight: 700;
            color: #59A4FF;
            margin-bottom: 18px;
        }
        </style>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([3, 2, 3])
    with center:
        username = st.text_input("Username", value="",
                                 placeholder="Enter your username")
        email = st.text_input(
            "Email", value="", placeholder="Enter your email")

        # _, col1, _ = st.columns([3, 1, 3])
        # _, col2, _ = st.columns([3, 1, 3])
        col1, col2 = st.columns(2)
        with col1:
            login_clicked = st.button("Login", use_container_width=True)
        with col2:
            if st.button("Back to Welcome", use_container_width=True):
                st.session_state["page"] = "welcome"
                st.rerun()

        if login_clicked:
            username = username.strip()
            email = email.strip()

            if not username or not email:
                st.error("Please enter both username and email.")
                return

            base_url = st.session_state["base_url"]
            payload = {"username": username, "email": email}

            try:
                r = requests.post(f"{base_url}/login",
                                  json=payload, timeout=60)
                data = r.json() if r.text else None
            except Exception as e:
                st.error(f"API call error: {e}")
                return

            if r.status_code >= 400:
                detail = data.get("detail", data) if isinstance(
                    data, dict) else data
                st.error(detail if isinstance(detail, str)
                         else json.dumps(detail, ensure_ascii=False))
                return

            if not isinstance(data, dict) or "user_id" not in data:
                st.error("Login failed, user_id not received.")
                return

            st.session_state["user"] = payload
            st.session_state["user_id"] = data["user_id"]
            st.session_state["logged_in"] = True
            st.session_state["page"] = "query"

            st.success("Login successful")
            st.rerun()
