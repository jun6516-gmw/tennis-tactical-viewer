import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors

# ----------------------------------------------------
# 打球速度に応じたカラーマップの定義
# ----------------------------------------------------
speed_thresholds = [0, 60, 100, 150]
colors_list = ["#ffffff", "#22c55e", "#eab308", "#ef4444"]
positions = [s / 150.0 for s in speed_thresholds]
ball_speed_cmap = mcolors.LinearSegmentedColormap.from_list("ball_speed_cmap", list(zip(positions, colors_list)))

def get_speed_color(speed_kmh):
    if speed_kmh is None or np.isnan(speed_kmh) or speed_kmh <= 0:
        return "#ffffff"
    norm_val = np.clip(speed_kmh / 150.0, 0.0, 1.0)
    return mcolors.to_hex(ball_speed_cmap(norm_val))

# OS依存のない日本語フォント設定
JP_FONTS = [
    'Yu Gothic', 'Meiryo', 'MS Gothic',
    'Hiragino Sans', 'Hiragino Kaku Gothic ProN',
    'Noto Sans CJK JP', 'TakaoGothic', 'IPAGothic', 'DejaVu Sans'
]
available_fonts = {f.name for f in fm.fontManager.ttflist}
selected_font = 'sans-serif'
for font in JP_FONTS:
    if font in available_fonts:
        selected_font = font
        plt.rcParams['font.family'] = font
        break

st.set_page_config(page_title="Tennis Match Tactical Visualizer", layout="wide")

STROKE_MAP = {
    'サーブ': 'Serve', 'フォアハンド': 'Forehand', 'バックハンド': 'Backhand',
    'フォアハンド ボレー': 'FH Volley', 'バックハンド ボレー': 'BH Volley',
    'スマッシュ': 'Smash', 'ドロップ': 'Drop Shot', 'フィード': 'Feed'
}
RESULT_MAP = {'イン': 'IN', 'アウト': 'OUT', 'ネット': 'NET'}

def translate_stroke(stroke):
    return STROKE_MAP.get(str(stroke), str(stroke))

def translate_result(result):
    return RESULT_MAP.get(str(result), str(result))

# サイドバー: ファイル読み込み
st.sidebar.header("📁 データ読み込み")
uploaded_file = st.sidebar.file_uploader("SwingVisionファイルを選択 (.xlsx / .csv)", type=["xlsx", "csv"])

if uploaded_file is None:
    st.markdown("""
    <div style="background-color: #f0f7ff; color: #1e3a8a; padding: 14px 16px; border-radius: 8px; border-left: 5px solid #2563eb; margin: 10px 0;">
        👈 <strong>左側のサイドバーから</strong> SwingVision のデータファイル（Excel または CSV）をアップロードしてください。
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if st.sidebar.button("🔄 キャッシュをクリアして再読込"):
    st.cache_data.clear()
    st.rerun()

def load_all_sheets(file):
    shots = pd.DataFrame()
    points = pd.DataFrame()
    games = pd.DataFrame()

    if file.name.endswith(".xlsx"):
        file.seek(0)
        xls = pd.ExcelFile(file)
        if "Shots" in xls.sheet_names:
            shots = pd.read_excel(xls, sheet_name="Shots")
        else:
            shots = pd.read_excel(xls, sheet_name=0)
            
        if "Points" in xls.sheet_names:
            points = pd.read_excel(xls, sheet_name="Points")
        if "Games" in xls.sheet_names:
            games = pd.read_excel(xls, sheet_name="Games")
    else:
        file.seek(0)
        shots = pd.read_csv(file)

    return shots, points, games

try:
    shots_df, points_df, games_df = load_all_sheets(uploaded_file)
except Exception as e:
    st.error(f"ファイルの読み込みに失敗しました: {e}")
    st.stop()

if shots_df.empty:
    st.error("Shotsデータが存在しません。")
    st.stop()

players = [p for p in shots_df['Player'].dropna().unique().tolist() if str(p).strip()]
if not players:
    st.error("有効なPlayerデータが存在しません。")
    st.stop()

st.sidebar.header("👤 プレイヤー視点設定")
target_player = st.sidebar.selectbox("手前側に固定するプレイヤーを選択", players, index=0)

# ----------------------------------------------------
# シーン構築 & スコア統合処理（Letを完全スキップ）
# ----------------------------------------------------
PT_MAP = {0: "0", 1: "15", 2: "30", 3: "40"}

def build_match_scenes_dataset(shots, points, focus_player):
    dataset = []

    # A. Pointsシートが存在する場合（公式スコア優先）
    if not points.empty and len(points) > 0 and 'Video Time' in points.columns:
        for idx, pt_row in points.iterrows():
            scene_id = int(pt_row['Point'])
            end_t = float(pt_row['Video Time'])
            dur = float(pt_row.get('Duration', 0.0))
            start_t = max(0.0, end_t - dur - 1.2) if dur > 0 else max(0.0, end_t - 8.0)
            
            sub_shots = shots[(shots['Video Time'] >= start_t) & (shots['Video Time'] <= end_t + 1.2)].copy()
            if sub_shots.empty:
                sub_shots = shots[shots['Point'] == scene_id].copy()
                
            sub_shots = sub_shots.sort_values('Video Time')
            sub_shots['Shot_Display'] = range(1, len(sub_shots) + 1)
            
            h_score = str(pt_row.get('Host Game Score', '0'))
            g_score = str(pt_row.get('Guest Game Score', '0'))
            game_num = pt_row.get('Game', 1)
            set_num = pt_row.get('Set', 1)
            score_str = f"Set {set_num} | Game {game_num} ({h_score}-{g_score})"
            
            winner = str(pt_row.get('Point Winner', ''))
            point_outcome = "取った" if winner == focus_player else "落とした"
            detail = str(pt_row.get('Detail', ''))
            
            finish_type = "その他"
            if "アウト" in detail or "out" in detail.lower():
                finish_type = "アウト"
            elif "ネット" in detail or "net" in detail.lower():
                finish_type = "ネット"
            elif "エース" in detail or "ace" in detail.lower():
                finish_type = "エース"
            elif "ウィナー" in detail or "winner" in detail.lower():
                finish_type = "ウィナー"

            dataset.append({
                'Scene': scene_id,
                'Score': score_str,
                'Point_Outcome': point_outcome,
                'Finish_Type': finish_type,
                'Total_Shots': len(sub_shots),
                'Detail': detail if detail else f"Winner: {winner}",
                'Shots_DF': sub_shots
            })

    # B. Pointsシートが無い場合のフォールバック（Shotsシートから通し計算、Letスキップ）
    else:
        # ノイズ（Shot 0）を除外
        valid_p_ids = []
        for p_id, grp in shots.groupby('Point'):
            f_row = grp.sort_values('Shot').iloc[0]
            if f_row['Shot'] == 1 and 'サーブ' in str(f_row['Stroke']):
                valid_p_ids.append(p_id)

        shots_clean = shots[shots['Point'].isin(valid_p_ids)].copy()
        temp_scenes = []
        for p_id in sorted(valid_p_ids):
            grp = shots_clean[shots_clean['Point'] == p_id].sort_values('Shot')
            last_s = grp.iloc[-1]
            last_p = str(last_s['Player'])
            last_res = translate_result(last_s['Result'])
            won = (last_p == focus_player and last_res == "IN") or (last_p != focus_player and last_res in ["OUT", "NET"])
            f_type = "アウト" if last_res == "OUT" else ("ネット" if last_res == "NET" else "エース")
            
            temp_scenes.append({
                'Scene': int(p_id),
                'Won': won,
                'Outcome': "取った" if won else "落とした",
                'Finish': f_type,
                'Detail': f"{last_p}: {translate_stroke(last_s['Stroke'])} -> {last_res}",
                'Shots': grp
            })

        sets_w, sets_l = 0, 0
        g_w, g_l = 0, 0
        p_w, p_l = 0, 0
        cur_server = None
        prev_won = True

        for idx, item in enumerate(temp_scenes):
            grp = item['Shots']
            first_s = grp.iloc[0]
            server = str(first_s['Player'])

            is_1st_fault = (len(grp) == 1 and 'first_serve' in str(first_s.get('Type', '')) and first_s['Result'] in ['ネット', 'アウト'])
            
            # レット判定
            is_let = False
            if len(grp) == 1 and 'サーブ' in str(first_s['Stroke']) and first_s['Result'] == 'イン':
                if idx + 1 < len(temp_scenes):
                    next_grp = temp_scenes[idx + 1]['Shots']
                    if not next_grp.empty:
                        next_f = next_grp.iloc[0]
                        if 'Video Time' in next_f and 'Video Time' in first_s:
                            dt = next_f['Video Time'] - first_s['Video Time']
                            if dt < 15.0 and next_f['Player'] == server and 'second_serve' in str(next_f.get('Type', '')):
                                is_let = True

            # レットの場合は表示リストにも含めず完全にスキップ
            if is_let:
                continue

            is_tb = (g_w == 6 and g_l == 6)
            if not is_tb and cur_server is not None and server != cur_server:
                if p_w > p_l:
                    g_w += 1
                elif p_l > p_w:
                    g_l += 1
                else:
                    if prev_won:
                        g_w += 1
                    else:
                        g_l += 1
                p_w, p_l = 0, 0
                
                if (g_w >= 6 and g_w - g_l >= 2) or (g_w == 7 and g_l == 5):
                    sets_w += 1
                    g_w, g_l = 0, 0
                elif (g_l >= 6 and g_l - g_w >= 2) or (g_l == 7 and g_w == 5):
                    sets_l += 1
                    g_w, g_l = 0, 0

            cur_server = server
            prev_won = item['Won']
            is_tb = (g_w == 6 and g_l == 6)

            if is_tb:
                pt_str = f"[TB {p_w}-{p_l}]"
            else:
                if p_w >= 3 and p_l >= 3:
                    pt_str = "(40-40 Deuce)" if p_w == p_l else ("(Ad-40)" if p_w == p_l + 1 else "(40-Ad)")
                else:
                    pt_str = f"({PT_MAP.get(p_w, '40')}-{PT_MAP.get(p_l, '40')})"

            tag = " [1st Fault]" if is_1st_fault else ""
            score_text = f"Set {sets_w + 1} | Game {g_w}-{g_l} {pt_str}{tag}"

            grp_copy = grp.copy()
            grp_copy['Shot_Display'] = grp_copy['Shot']

            dataset.append({
                'Scene': item['Scene'],
                'Score': score_text,
                'Point_Outcome': item['Outcome'],
                'Finish_Type': item['Finish'],
                'Total_Shots': len(grp),
                'Detail': item['Detail'],
                'Shots_DF': grp_copy
            })

            if not is_1st_fault:
                if item['Won']:
                    p_w += 1
                else:
                    p_l += 1

                if is_tb:
                    if p_w >= 7 and p_w - p_l >= 2:
                        sets_w += 1
                        g_w, g_l, p_w, p_l = 0, 0, 0, 0
                    elif p_l >= 7 and p_l - p_w >= 2:
                        sets_l += 1
                        g_w, g_l, p_w, p_l = 0, 0, 0, 0

    return dataset

match_scenes = build_match_scenes_dataset(shots_df, points_df, target_player)

if not match_scenes:
    st.error("有効なシーンデータが見つかりませんでした。")
    st.stop()

full_meta_df = pd.DataFrame([{k: v for k, v in item.items() if k != 'Shots_DF'} for item in match_scenes])
shots_dict = {item['Scene']: item['Shots_DF'] for item in match_scenes}

# ----------------------------------------------------
# サイドバー: フィルタ
# ----------------------------------------------------
st.sidebar.header("🔍 フィルタ設定")

c_all = len(full_meta_df)
c_won = len(full_meta_df[full_meta_df['Point_Outcome'] == '取った'])
c_lost = len(full_meta_df[full_meta_df['Point_Outcome'] == '落とした'])

outcome_map = {
    f"すべて ({c_all})": "すべて",
    f"取った ({c_won})": "取った",
    f"落とした ({c_lost})": "落とした"
}
chosen_outcome_label = st.sidebar.selectbox("■ シーン勝敗", list(outcome_map.keys()))
sel_outcome = outcome_map[chosen_outcome_label]

if sel_outcome == "すべて":
    df_s1 = full_meta_df
else:
    df_s1 = full_meta_df[full_meta_df['Point_Outcome'] == sel_outcome]

finish_options = ["すべて"] + [f for f in df_s1['Finish_Type'].unique() if f != "その他"]
chosen_finish = st.sidebar.selectbox("■ 決まり方", finish_options)

if chosen_finish == "すべて":
    final_df = df_s1
else:
    final_df = df_s1[df_s1['Finish_Type'] == chosen_finish]

if final_df.empty:
    st.warning("⚠️ 選択した条件に一致するシーンがありません。")
    st.stop()

scene_list = final_df['Scene'].tolist()

filter_sig = f"{sel_outcome}_{chosen_finish}"
if "last_filter_sig" not in st.session_state or st.session_state.last_filter_sig != filter_sig:
    st.session_state.last_filter_sig = filter_sig
    st.session_state.cur_scene_idx = 0

if "cur_scene_idx" not in st.session_state or st.session_state.cur_scene_idx >= len(scene_list):
    st.session_state.cur_scene_idx = 0

st.sidebar.markdown("---")
st.sidebar.header("🎨 表示設定")
view_mode = st.sidebar.radio("描画モード", ["全ラリー表示", "決着ラスト2打のみ表示"], index=0)

if "main_scene_select" not in st.session_state or st.session_state.main_scene_select not in scene_list:
    st.session_state.main_scene_select = scene_list[st.session_state.cur_scene_idx]

def go_prev_scene():
    if st.session_state.cur_scene_idx > 0:
        st.session_state.cur_scene_idx -= 1
        st.session_state.main_scene_select = scene_list[st.session_state.cur_scene_idx]

def go_next_scene():
    if st.session_state.cur_scene_idx < len(scene_list) - 1:
        st.session_state.cur_scene_idx += 1
        st.session_state.main_scene_select = scene_list[st.session_state.cur_scene_idx]

def on_main_select():
    chosen = st.session_state.main_scene_select
    if chosen in scene_list:
        st.session_state.cur_scene_idx = scene_list.index(chosen)

# CSS: ナビゲーションバーの固定
st.markdown("""
<style>
.block-container { padding-top: 3.5rem !important; padding-bottom: 1rem !important; }
[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 8px !important;
    width: 220px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(1),
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(3) {
    flex: 0 0 44px !important;
    width: 44px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(2) {
    flex: 0 0 110px !important;
    width: 110px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 38px !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

@media (max-width: 768px) {
    [data-testid="stPlotlyChart"], div.element-container:has(figure) {
        width: 80% !important; margin-left: auto !important; margin-right: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ナビゲーションUI（3カラム）
col_prev, col_sel, col_next = st.columns([1, 2, 1])
with col_prev:
    st.button("◀", key="main_prev", on_click=go_prev_scene, use_container_width=True)
with col_sel:
    st.selectbox("Scene #", options=scene_list, format_func=lambda x: f"Scene {x}", key="main_scene_select", on_change=on_main_select, label_visibility="collapsed")
with col_next:
    st.button("▶", key="main_next", on_click=go_next_scene, use_container_width=True)

selected_scene = scene_list[st.session_state.cur_scene_idx]
s_info = full_meta_df[full_meta_df['Scene'] == selected_scene].iloc[0]
s_shots = shots_dict.get(selected_scene, pd.DataFrame())

col_court, col_info = st.columns([1.1, 1.0])

# ====================================================
# 【左側】コート描画
# ====================================================
with col_court:
    NET_Y = 11.885
    focal_shots = s_shots[s_shots['Player'] == target_player]
    is_far = False
    if not focal_shots.empty and focal_shots['Hit (y)'].mean() > NET_Y:
        is_far = True

    records = []
    for idx, row in s_shots.iterrows():
        s_num = int(row.get('Shot_Display', row.get('Shot', 1)))
        hx, hy = row['Hit (x)'], row['Hit (y)']
        bx, by = row['Bounce (x)'], row['Bounce (y)']
        if is_far:
            hx, hy = -hx, 23.77 - hy
            bx, by = -bx, 23.77 - by
        records.append({
            'shot': s_num,
            'player': str(row['Player']),
            'stroke': translate_stroke(row['Stroke']),
            'speed': row['Speed (KM/H)'],
            'result': translate_result(row['Result']),
            'hx': hx, 'hy': hy, 'bx': bx, 'by': by
        })

    if view_mode == "決着ラスト2打のみ表示":
        records = records[-min(2, len(records)):]

    fig, ax = plt.subplots(figsize=(5.5, 9.5), facecolor='#0f172a')
    ax.set_facecolor('#0f172a')

    # コートライン描画
    rect_court = patches.Rectangle((-5.485, 0), 10.97, 23.77, linewidth=2, edgecolor='#64748b', facecolor='#1e3a8a', alpha=0.9)
    ax.add_patch(rect_court)
    rect_singles = patches.Rectangle((-4.115, 0), 8.23, 23.77, linewidth=1.5, edgecolor='#cbd5e1', facecolor='none')
    ax.add_patch(rect_singles)

    ax.plot([-5.8, 5.8], [NET_Y, NET_Y], color='#ffffff', linewidth=3.0, zorder=10)
    ax.text(6.0, NET_Y, 'NET', color='#ffffff', verticalalignment='center', fontsize=9, fontweight='bold')

    ax.plot([-4.115, 4.115], [5.485, 5.485], color='#94a3b8', linewidth=1.5)
    ax.plot([-4.115, 4.115], [18.285, 18.285], color='#94a3b8', linewidth=1.5)
    ax.plot([0, 0], [5.485, 18.285], color='#94a3b8', linewidth=1.5)
    ax.plot([0, 0], [0, 0.4], color='#cbd5e1', linewidth=1.5)
    ax.plot([0, 0], [23.37, 23.77], color='#cbd5e1', linewidth=1.5)

    color_focal = '#38bdf8
