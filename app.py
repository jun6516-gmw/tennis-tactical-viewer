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
/* 中央のスコア表示枠 */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
    flex: 1 1 auto !important;
    max-width: 260px !important;
}
div[data-testid="stHorizontalBlock"] button {
    height: 40px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}
/* スコア表示ボタン（中央）の見た目を整える */
.score-badge {
    height: 40px;
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 15px;
    color: #1e293b;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

st.title("ナビゲーション検証")

cur_scene = scene_list[st.session_state.cur_idx]
cur_score_str = dummy_scores[cur_scene]

# ナビゲーションバー
col1, col2, col3 = st.columns([1, 4, 1], gap="small")
with col1:
    st.button("◀", key="btn_prev", on_click=go_prev, use_container_width=True)
with col2:
    # 中央に現在のスコアを明快にバッジ表示
    st.markdown(f'<div class="score-badge">Sc.{cur_scene} {cur_score_str}</div>', unsafe_allow_html=True)
with col3:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

# 任意の位置へ瞬時にジャンプできるスライダー（PCでもスマホでも現在位置と100%完全連動）
new_scene = st.select_slider(
    "シーン移動",
    options=scene_list,
    value=cur_scene,
    format_func=lambda s: f"{s}",
    label_visibility="collapsed"
)
if new_scene != cur_scene:
    st.session_state.cur_idx = scene_list.index(new_scene)
    st.rerun()

st.write(f"現在表示中: **Scene {cur_scene} ({cur_score_str})**")
