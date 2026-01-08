import streamlit as st

from login import render_login
from resigter import render_register
from input_query import render_query
from result_recommedation import render_result
from logout import do_logout
# Make sure you have a welcome.py with render_welcome function
from welcome import render_welcome
import base64

st.set_page_config(page_title="Trợ lý Dinh dưỡng AI Capstone", layout="wide")
st.markdown(
    "<h1 style='text-align: center; font-family: Helvetica; font-size: 60px;'>Trợ lý Dinh dưỡng</h1>"
    "<h6 style='text-align: center;'>Được phát triển bởi GFA25AI11-Team</h6>",
    unsafe_allow_html=True
)


def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


img_path = r"./Frontend/background_image/635918.jpg"
img_base64 = get_base64_of_bin_file(img_path)


# Custom CSS: background image + blur sidebar
st.markdown(
    f"""
    <style>
    /* Background image for main app */
    body, .stApp {{
        background-image: url("data:image/jpg;base64,{img_base64}");
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    /* Blur sidebar */
    section[data-testid="stSidebar"] {{
        backdrop-filter: blur(8px);
        background: rgba(30, 30, 40, 0.5) !important;
    }}

    /* Sidebar buttons ONLY */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
        font-size: 40px !important;        /* text size */
        font-weight: 700 !important;
        padding: 14px 12px !important;     /* button thickness */
        min-height: 56px !important;       /* button height */
        border-radius: 12px !important;
        background: rgba(255, 255, 255, 0.15) !important;
        color: #fff !important;
        border: 14 !important;
        width: 100% !important;
    }}

    /* Hover effect */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {{
        background: rgba(255, 255, 255, 0.28) !important;
        transform: translateY(-1px);
        transition: all 0.15s ease-in-out;
    }}

    /* Click effect */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:active {{
        transform: translateY(0px);
        background: rgba(255, 255, 255, 0.22) !important;
    }}

    /* Fix sidebar width and hide resizer */
    section[data-testid="stSidebar"] {{
        min-width: 350px !important;
        max-width: 350px !important;
        width: 350px !important;
    }}
    
    /* Hide sidebar resizer handle */
    div[data-testid="stSidebarNav"] ~ div[aria-label="Resize sidebar"] {{
        display: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- init session state ----
defaults = {
    "logged_in": False,
    "user": {},          # <- đổi từ None sang {}
    "user_id": None,
    "page": "welcome",
    "base_url": "http://127.0.0.1:8000",
    "query": "",
    "last_result": None,
    "busy": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _qp_get(name: str):
    try:
        v = st.query_params.get(name)
    except Exception:
        # older streamlit fallback
        v = st.experimental_get_query_params().get(name)
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _restore_auth_from_query_params() -> None:
    if st.session_state.get("logged_in"):
        return

    user_id_raw = _qp_get("user_id")
    if not user_id_raw:
        return

    try:
        user_id = int(user_id_raw)
    except Exception:
        return

    page = _qp_get("page")

    st.session_state["user_id"] = user_id
    # Do not restore username/email from URL to avoid leaking PII.
    st.session_state["user"] = st.session_state.get("user") or {}
    st.session_state["logged_in"] = True

    # Best-effort cleanup of any old sensitive params still in the URL.
    try:
        st.query_params.pop("username", None)
        st.query_params.pop("email", None)
    except Exception:
        pass

    # After refresh, avoid landing on auth screens
    if page in ("query", "result"):
        st.session_state["page"] = page
    elif st.session_state.get("page") in ("welcome", "login", "register", "logout"):
        st.session_state["page"] = "query"


_restore_auth_from_query_params()


# Hide sidebar if not logged in or on welcome/login/register/logout pages
if (not st.session_state.get("logged_in")) or (st.session_state.get("page") in ("welcome", "login", "register", "logout")):
    st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

# ---- sidebar: backend + nav ----
with st.sidebar:
    st.subheader("Menu")
    sidebar_disabled = bool(st.session_state.get("busy"))

    if st.session_state["logged_in"]:
        if st.button("Truy vấn", use_container_width=True, disabled=sidebar_disabled):
            st.session_state["page"] = "query"
            try:
                st.query_params["page"] = "query"
            except Exception:
                st.experimental_set_query_params(page="query")
            st.rerun()
        if st.button("Lịch sử", use_container_width=True, disabled=sidebar_disabled):
            st.session_state["page"] = "result"
            st.session_state["history_user_payload"] = None
            st.session_state["force_reload_history"] = True
            try:
                st.query_params["page"] = "result"
            except Exception:
                st.experimental_set_query_params(page="result")
            st.rerun()
        if st.button("Đăng xuất", use_container_width=True, disabled=sidebar_disabled):
            do_logout()

    user = st.session_state.get("user") or {}
    username_display = user.get("username") or "Khách"
    st.markdown(
        f"""
        <div style='text-align: center; color: #fff; font-size: 20px; position: fixed; bottom: 50px; width: 80%;'>
            ☃️ Xin chào {username_display} ❄️
        </div>
        """,
        unsafe_allow_html=True
    )


# ---- router ----
if st.session_state["page"] == "welcome":
    render_welcome()
elif not st.session_state["logged_in"]:
    if st.session_state["page"] == "register":
        render_register()
    else:
        render_login()
else:
    if st.session_state["page"] == "query":
        render_query()
    else:
        render_result()
