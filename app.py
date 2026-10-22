import streamlit as st

st.set_page_config(page_title="Nav Only Test", layout="centered")

# テスト用データ (1〜30)
scene_list = list(range(1, 31))

if "cur_idx" not in st.session_state:
    st.session_state.cur_idx = 7  # 初期値: Scene 8

def go_prev():
    if st.session_state.cur_idx > 0:
        st.session_state.cur_idx -= 1
        st.session_state.scene_select = scene_list[st.session_state.cur_idx]

def go_next():
    if st.session_state.cur_idx < len(scene_list) - 1:
        st.session_state.cur_idx += 1
        st.session_state.scene_select = scene_list[st.session_state.cur_idx]

def on_select():
    st.session_state.cur_idx = scene_list.index(st.session_state.scene_select)

# ----------------------------------------------------
# 1行横並び固定のスタイル
# ----------------------------------------------------
st.markdown("""
<style>
/* スマホ幅でも縦積みにせず、必ず1行で横並びを維持する */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
}

/* スマホ用の最小幅（縦積みの原因）を解除 */
div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
    flex: 1 1 auto !important;
}

/* ◀ と ▶ は 46px 固定 */
div[data-testid="stHorizontalBlock"] > div:nth-child(1),
div[data-testid="stHorizontalBlock"] > div:nth-child(3) {
    flex: 0 0 46px !important;
    width: 46px !important;
}

/* 中央のセレクトボックス幅 */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
    flex: 1 1 auto !important;
    max-width: 180px !important;
}

/* ボタンの高さ */
div[data-testid="stHorizontalBlock"] button {
    height: 40px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Scene ナビゲーション表示")

# ◀ / Scene # / ▶ の横並び配置
col_prev, col_sel, col_next = st.columns([1, 2, 1], gap="small")

with col_prev:
    st.button("◀", key="btn_prev", on_click=go_prev, use_container_width=True)

with col_sel:
    st.selectbox(
        "Scene",
        options=scene_list,
        index=st.session_state.cur_idx,
        format_func=lambda x: f"Scene {x}",
        key="scene_select",
        on_change=on_select,
        label_visibility="collapsed"
    )

with col_next:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

st.write("---")
st.write(f"### 現在選択中: **Scene {scene_list[st.session_state.cur_idx]}**")
