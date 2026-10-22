import streamlit as st

st.set_page_config(page_title="Nav Test", layout="centered")

# テスト用シーンデータ
scene_list = list(range(1, 31))
# テスト用短縮スコア
dummy_scores = {i: f"0-0 | {i//6}-{i%6} | {15*(i%4)}-{15*((i+1)%4)}" for i in scene_list}

if "cur_idx" not in st.session_state:
    st.session_state.cur_idx = 7  # 初期値

def go_prev():
    if st.session_state.cur_idx > 0:
        st.session_state.cur_idx -= 1

def go_next():
    if st.session_state.cur_idx < len(scene_list) - 1:
        st.session_state.cur_idx += 1

st.markdown("""
<style>
/* 1行横並び固定 */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
}
div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}
/* ◀ と ▶ は 46px 固定 */
div[data-testid="stHorizontalBlock"] > div:nth-child(1),
div[data-testid="stHorizontalBlock"] > div:nth-child(3) {
    flex: 0 0 46px !important;
    width: 46px !important;
}
/* 中央のプルダウン幅 */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
    flex: 1 1 auto !important;
    max-width: 250px !important;
}
div[data-testid="stHorizontalBlock"] button {
    height: 40px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Scene ナビゲーション表示")

# ナビゲーションバー
col1, col2, col3 = st.columns([1, 4, 1], gap="small")
with col1:
    st.button("◀", key="btn_prev", on_click=go_prev, use_container_width=True)

with col2:
    # 選択位置のずれを防ぐため、動的なキーで直接現在位置を束縛
    chosen_scene = st.selectbox(
        "Scene",
        options=scene_list,
        index=st.session_state.cur_idx,
        format_func=lambda s: f"Sc.{s}  {dummy_scores[s]}",
        key=f"scene_selector_{st.session_state.cur_idx}",
        label_visibility="collapsed"
    )
    if chosen_scene != scene_list[st.session_state.cur_idx]:
        st.session_state.cur_idx = scene_list.index(chosen_scene)
        st.rerun()

with col3:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

cur_s = scene_list[st.session_state.cur_idx]
st.write("---")
st.write(f"### 現在選択中: **Scene {cur_s} ({dummy_scores[cur_s]})**")
