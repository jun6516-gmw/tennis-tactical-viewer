import streamlit as st

st.set_page_config(page_title="Nav Only Test", layout="centered")

# テスト用シーンデータ (1〜30)
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
# 最小限の安全なスタイル設定
# ----------------------------------------------------
st.markdown("""
<style>
/* ボタンの高さをセレクトボックス（38〜40px）に揃える */
div[data-testid="stHorizontalBlock"] button {
    height: 40px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Scene ナビゲーション表示")

# 左右ボタンを小さく(1)、中央を広く(2)割り当て
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
