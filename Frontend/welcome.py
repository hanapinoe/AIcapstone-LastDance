import streamlit as st


def render_welcome():
    # Chỉ style riêng cho màn welcome (tránh làm các nút trang khác bị phóng to)
    st.markdown(
        """
        <style>
        /* Bắt đúng wrapper button của Streamlit */
        div[data-testid="stButton"] > button,
        div.stButton > button {
            font-size: 15px !important;
            line-height: 1.1 !important;
            padding: 10px 5px !important;
        }

        /* Ép luôn chữ nằm bên trong */
        div[data-testid="stButton"] > button * {
            font-size: 25px !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, col1, _ = st.columns([3, 2, 3])
    _, col2, _ = st.columns([3, 2, 3])
    with col1:
        if st.button("Đăng nhập", key="welcome_login", use_container_width=True):
            st.session_state["page"] = "login"
            st.rerun()
    with col2:
        if st.button("Đăng ký", key="welcome_register", use_container_width=True):
            st.session_state["page"] = "register"
            st.rerun()
