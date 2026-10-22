import streamlit as st

st.set_page_config(page_title="Nav Test", layout="wide")

scene_list = list(range(1, 31))
if "cur_idx" not in st.session_state:
    st.session_state.cur_idx = 7  # 初期表示：8

def go_prev():
    if st.session_state.cur_idx > 0:
        st.session_state.cur_idx -= 1

def go_next():
    if st.session_state.cur_idx < len(scene_list) - 1:
        st.session_state.cur_idx += 1

def on_change():
    st.session_state.cur_idx = scene_list.index(st.session_state.test_select)

# ----------------------------------------------------
# 調整する数値（ここを変更してテストします）
# ----------------------------------------------------
btn_w = 44   # ◀ ▶ ボタンの幅(px)
sel_w = 120  # セレクトボックスの幅(px)
h = 40       # 高さ(px)

st.markdown(f"""
<style>
/* カラムブロック：折り返し防止 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 8px !important;
    width: 100% !important;
}}

/* スマホ用の自動改行を解除 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div {{
    min-width: 0 !important;
    flex-shrink: 0 !important;
}}

/* ◀ と ▶ の幅 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(1),
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(3) {{
    width: {btn_w}px !important;
    max-width: {btn_w}px !important;
}}

/* 中央プルダウン枠の幅 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(2) {{
    width: {sel_w}px !important;
    max-width: {sel_w}px !important;
}}

/* ボタン高さ・装飾 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {{
    height: {h}px !important;
    width: 100% !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}}
</style>
""", unsafe_allow_html=True)

st.write("### ナビゲーション表示テスト")

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.button("◀", key="btn_prev", on_click=go_prev, use_container_width=True)
with col2:
    st.selectbox(
        "Scene",
        options=scene_list,
        index=st.session_state.cur_idx,
        format_func=lambda x: f"Scene {x}",  # 「8」だけにする場合はこの行を削除
        key="test_select",
        on_change=on_change,
        label_visibility="collapsed"
    )
with col3:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

st.write(f"現在の選択: **Scene {scene_list[st.session_state.cur_idx]}**")
