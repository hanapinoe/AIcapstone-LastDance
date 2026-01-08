import json
import requests
import streamlit as st
import html

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
            "request": "Yêu cầu",
            "dish_name": "Tên món",
            "chosen_option": "Lựa chọn của hệ thống",
            "explaination": "Giải thích",
            "time": "Thời gian",
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


def _cell_to_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd is not None and pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_glass_table(df):
    # HTML table so long text wraps instead of being truncated.
    cols = list(df.columns)
    width_map = {
        "Yêu cầu": 24,
        "Tên món": 12,
        "Lựa chọn của hệ thống": 18,
        "Giải thích": 36,
        "Thời gian": 10,
    }
    default_w = max(10, int(100 / max(len(cols), 1)))

    colgroup = "".join(
        f"<col style='width:{width_map.get(str(c).lower(), default_w)}%'>" for c in cols
    )

    thead = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)

    body_rows = []
    for row in df.itertuples(index=False, name=None):
        tds = []
        for v in row:
            txt = _cell_to_text(v)
            safe = html.escape(txt).replace("\n", "<br/>")
            tds.append(f"<td>{safe}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")

    return f"""
    <div class="glass-table-wrapper">
      <table class="glass-table">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{thead}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    """


def _white_notice(text: str):
    safe = html.escape(text or "").replace("\n", "<br/>")
    st.markdown(
        f"""
        <div style='background:#fff; color:#222; padding:12px 16px; border-radius:8px;
                    border:1px solid #eee; text-align:left; line-height:1.4;'>
            <div style='font-weight:700; margin-bottom:6px;'>Thông báo</div>
            <div>{safe}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result():
    _ensure_busy_state()
    disabled = bool(st.session_state.get("busy"))

    if not st.session_state.get("logged_in"):
        st.warning("Bạn cần đăng nhập để xem lịch sử.")
        st.session_state["page"] = "login"
        st.rerun()
        return

    st.markdown(
        """
        <div style='margin-top: 0px; text-align: center; color: #fff; font-size: 40px;'>
            Lịch sử truy vấn
        </div>
        """,
        unsafe_allow_html=True
    )

    # Glass table CSS (wrap long text, keep blurred style)
    st.markdown(
        """
        <style>
        .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .glass-table-wrapper {
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            background: rgba(30, 30, 40, 0.35);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 12px;
            box-shadow: 0 4px 32px 0 rgba(0,0,0,0.18);
            overflow-x: auto;
        }
        .glass-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }
        .glass-table thead th {
            color: #FC9249;
            font-weight: 700;
            font-size: 0.95rem;
            text-align: left;
            padding: 10px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.18);
            white-space: nowrap;
        }
        .glass-table tbody td {
            color: #fff;
            font-size: 0.95rem;
            padding: 10px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            vertical-align: top;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: break-word;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("pending_error"):
        _white_notice(st.session_state["pending_error"])
        st.session_state["pending_error"] = None

    # Execution phase for seeding one demo record (so History isn't empty)
    if st.session_state.get("pending_action") == "seed_demo":
        base_url = st.session_state["base_url"]
        user_id = st.session_state.get("user_id")
        demo_query = (st.session_state.get("query") or "").strip(
        ) or "Gợi ý món ăn/uống cho demo"

        with st.spinner("Đang tạo dữ liệu mẫu..."):
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
                st.session_state["pending_error"] = f"Không thể tạo dữ liệu mẫu: {e}"
            finally:
                st.session_state["pending_action"] = None
                st.session_state["busy"] = False

        st.rerun()

    # Execution phase for loading merged history
    if st.session_state.get("pending_action") == "history_user":
        base_url = st.session_state["base_url"]
        user_id = st.session_state.get("user_id")

        with st.spinner("Đang tải lịch sử..."):
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
                st.session_state["pending_error"] = f"Lỗi gọi API: {e}"
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
                        ⚠️ Không tìm thấy bản ghi lịch sử nào
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        elif df is None:
            st.json(payload)
        else:
            col1, col2, col3 = st.columns([1, 8, 1])
            with col2:
                st.markdown(_render_glass_table(
                    df.fillna("")), unsafe_allow_html=True)

    if st.session_state.get("page") == "result" and not st.session_state.get("query"):
        _white_notice("Vui lòng nhập truy vấn trước khi đề xuất.")
