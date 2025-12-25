import json
import requests
import streamlit as st


def render_register():
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

        # _, col1, _ = st.columns([1, 2, 1])
        # _, col2, _ = st.columns([1, 2, 1])
        col1, col2 = st.columns(2)
        register_clicked = col1.button("Register", use_container_width=True)
        back_clicked = col2.button("Back", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    if back_clicked:
        st.session_state["page"] = "welcome"
        st.rerun()

    error_msg = None
    if register_clicked:
        if not username.strip() or not email.strip():
            error_msg = "Please enter both username and email."
        else:
            payload = {"username": username.strip(), "email": email.strip()}
            base_url = st.session_state["base_url"]
            try:
                r = requests.post(f"{base_url}/register",
                                  json=payload, timeout=60)
                data = r.json() if r.text else None
            except Exception as e:
                error_msg = f"API Error: {e}"
            else:
                if r.status_code >= 400:
                    detail = data.get("detail", data) if isinstance(
                        data, dict) else data
                    error_msg = detail if isinstance(
                        detail, str) else json.dumps(detail, ensure_ascii=False)
                elif data is None or "user_id" not in data:
                    error_msg = "Registration failed, could not retrieve user_id."
                else:
                    st.success(
                        f"Registration successful! User ID: {data.get('user_id')}")
                    st.session_state["page"] = "login"
                    st.rerun()

    if error_msg:
        st.markdown(
            f"""
            <div style="
                margin: 16px auto 0 auto;
                max-width: 420px;
                background: rgba(255, 0, 0, 0.15);
                color: #ff3333;
                border-radius: 10px;
                padding: 12px 16px;
                text-align: center;
                font-weight: 600;">
                {error_msg}
            </div>
            """,
            unsafe_allow_html=True
        )
