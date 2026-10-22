import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Nav Test", layout="centered")

# テスト用シーンデータ
scene_list = list(range(1, 31))
dummy_scores = {i: f"0-0 | {i//6}-{i%6} | {15*(i%4)}-{15*((i+1)%4)}" for i in scene_list}

if "cur_idx" not in st.session_state:
    st.session_state.cur_idx = 7  # 初期値: Scene 8

# クエリパラメータによるセレクト変更検知
query_params = st.query_params
if "sel_scene" in query_params:
    try:
        new_s = int(query_params["sel_scene"])
        if new_s in scene_list:
            st.session_state.cur_idx = scene_list.index(new_s)
    except Exception:
        pass
    st.query_params.clear()

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
/* 中央のセレクト枠 */
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

cur_scene = scene_list[st.session_state.cur_idx]

# ネイティブセレクトボックス用のHTML生成
options_html = "".join([
    f'<option value="{s}" {"selected" if s == cur_scene else ""}>Sc.{s} {dummy_scores[s]}</option>'
    for s in scene_list
])

native_select_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}
select {{
    width: 100%;
    height: 40px;
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0 10px;
    font-size: 14px;
    font-weight: 500;
    color: #1e293b;
    outline: none;
    cursor: pointer;
    box-sizing: border-box;
}}
select:hover {{
    border-color: #94a3b8;
}}
</style>
</head>
<body>
<select onchange="window.parent.location.search = '?sel_scene=' + this.value;">
{options_html}
</select>
</body>
</html>
"""

col1, col2, col3 = st.columns([1, 4, 1], gap="small")
with col1:
    st.button("◀", key="btn_prev", on_click=go_prev, use_container_width=True)

with col2:
    components.html(native_select_html, height=42)

with col3:
    st.button("▶", key="btn_next", on_click=go_next, use_container_width=True)

st.write("---")
st.write(f"### 現在選択中: **Scene {cur_scene} ({dummy_scores[cur_scene]})**")
