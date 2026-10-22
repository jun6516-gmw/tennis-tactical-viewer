import streamlit as st

st.set_page_config(page_title="Nav Test", layout="wide")

scene_list = list(range(1, 31))
if "cur_idx" not in st.session_state:
    st.session_state.cur_idx = 7  # 初期表示: Scene 8

def go_prev():
    if st.session_state.cur_idx > 0:
        st.session_state.cur_idx -= 1

def go_next():
    if st.session_state.cur_idx < len(scene_list) - 1:
        st.session_state.cur_idx += 1

def on_change():
    st.session_state.cur_idx = scene_list.index(st.session_state.test_select)

btn_w = 44   # ボタン幅
sel_w = 130  # プルダウン枠幅
h = 40       # 高さ

st.markdown(f"""
<style>
/* 1. 横並びの固定 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 8px !important;
    width: 100% !important;
}}

/* 2. カラム幅の固定 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div {{
    min-width: 0 !important;
    flex-shrink: 0 !important;
}}
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(1),
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(3) {{
    width: {btn_w}px !important;
    max-width: {btn_w}px !important;
}}
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(2) {{
    width: {sel_w}px !important;
    max-width: {sel_w}px !important;
}}

/* ★ 3. これが決定打：消えていた内部の文字コンテナを強制表示させる */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-baseweb="select"] div[aria-haspopup="listbox"] > div:first-child {{
    display: block !important;
    min-width: 60px !important;
    flex-shrink: 0 !important;
    white-space: nowrap !important;
    overflow: visible !important;
}}

/* 4. ボタンのスタイル */
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
        format_func=lambda x: f"Scene {x}",
        key="test_select",
        on_change=on_change,
        label_visibility="collapsed"
    )
with col3:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

st.write(f"現在の選択: **Scene {scene_list[st.session_state.cur_idx]}**")
