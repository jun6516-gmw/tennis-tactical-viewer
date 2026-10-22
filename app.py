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

# キャッシュのクリアボタン（データ更新時のトラブル防止）
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
# PointsシートとShotsシートの統合処理
# ----------------------------------------------------
PT_MAP = {0: "0", 1: "15", 2: "30", 3: "40"}

def build_match_points_dataset(shots, points, focus_player):
    dataset = []

    # A. Pointsシートが存在し、かつデータ行がある場合
    if not points.empty and len(points) > 0 and 'Video Time' in points.columns:
        for idx, pt_row in points.iterrows():
            pt_id = int(pt_row['Point'])
            end_t = float(pt_row['Video Time'])
            dur = float(pt_row.get('Duration', 0.0))
            start_t = max(0.0, end_t - dur - 1.2) if dur > 0 else max(0.0, end_t - 8.0)
            
            # 時間範囲で該当ショットを抽出
            sub_shots = shots[(shots['Video Time'] >= start_t) & (shots['Video Time'] <= end_t + 1.2)].copy()
            if sub_shots.empty:
                sub_shots = shots[shots['Point'] == pt_id].copy()
                
            sub_shots = sub_shots.sort_values('Video Time')
            sub_shots['Shot_Display'] = range(1, len(sub_shots) + 1)
            
            # スコア文字列
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
                'Point': pt_id,
                'Score': score_str,
                'Point_Outcome': point_outcome,
                'Finish_Type': finish_type,
                'Total_Shots': len(sub_shots),
                'Detail': detail if detail else f"Winner: {winner}",
                'Shots_DF': sub_shots
            })

    # B. Pointsシートが無い場合のフォールバック（Shotsシートから通し計算）
    else:
        valid_p_ids = []
        for p_id, grp in shots.groupby('Point'):
            f_row = grp.sort_values('Shot').iloc[0]
            if f_row['Shot'] == 1 and 'サーブ' in str(f_row['Stroke']):
                valid_p_ids.append(p_id)

        shots_clean = shots[shots['Point'].isin(valid_p_ids)].copy()
        temp_points = []
        for p_id in sorted(valid_p_ids):
            grp = shots_clean[shots_clean['Point'] == p_id].sort_values('Shot')
            last_s = grp.iloc[-1]
            last_p = str(last_s['Player'])
            last_res = translate_result(last_s['Result'])
            won = (last_p == focus_player and last_res == "IN") or (last_p != focus_player and last_res in ["OUT", "NET"])
            f_type = "アウト" if last_res == "OUT" else ("ネット" if last_res == "NET" else "エース")
            
            temp_points.append({
                'Point': int(p_id),
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

        for idx, item in enumerate(temp_points):
            grp = item['Shots']
            first_s = grp.iloc[0]
            server = str(first_s['Player'])

            is_1st_fault = (len(grp) == 1 and 'first_serve' in str(first_s.get('Type', '')) and first_s['Result'] in ['ネット', 'アウト'])
            
            is_let = False
            if len(grp) == 1 and 'サーブ' in str(first_s['Stroke']) and first_s['Result'] == 'イン':
                if idx + 1 < len(temp_points):
                    next_grp = temp_points[idx + 1]['Shots']
                    if not next_grp.empty:
                        next_f = next_grp.iloc[0]
                        if 'Video Time' in next_f and 'Video Time' in first_s:
                            dt = next_f['Video Time'] - first_s['Video Time']
                            if dt < 15.0 and next_f['Player'] == server and 'second_serve' in str(next_f.get('Type', '')):
                                is_let = True

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

            tag = " [1st Fault]" if is_1st_fault else (" [Let]" if is_let else "")
            score_text = f"Set {sets_w + 1} | Game {g_w}-{g_l} {pt_str}{tag}"

            grp_copy = grp.copy()
            grp_copy['Shot_Display'] = grp_copy['Shot']

            dataset.append({
                'Point': item['Point'],
                'Score': score_text,
                'Point_Outcome': item['Outcome'],
                'Finish_Type': item['Finish'],
                'Total_Shots': len(grp),
                'Detail': item['Detail'],
                'Shots_DF': grp_copy
            })

            if not is_1st_fault and not is_let:
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

match_points = build_match_points_dataset(shots_df, points_df, target_player)

if not match_points:
    st.error("有効なポイントデータが見つかりませんでした。")
    st.stop()

full_meta_df = pd.DataFrame([{k: v for k, v in item.items() if k != 'Shots_DF'} for item in match_points])
shots_dict = {item['Point']: item['Shots_DF'] for item in match_points}

# ----------------------------------------------------
# サイドバー: フィルタ
# ----------------------------------------------------
st.sidebar.header("🔍 フィルタ設定")

c_all = len(full_meta_df)
c_won = len(full_meta_df[full_meta_df['Point_Outcome'] == '取った'])
c_lost = len(full_meta_df[full_meta_df['Point_Outcome'] == '落とした'])

point_map = {
    f"すべて ({c_all})": "すべて",
    f"取った ({c_won})": "取った",
    f"落とした ({c_lost})": "落とした"
}
chosen_point_label = st.sidebar.selectbox("■ ポイント", list(point_map.keys()))
sel_point = point_map[chosen_point_label]

if sel_point == "すべて":
    df_s1 = full_meta_df
else:
    df_s1 = full_meta_df[full_meta_df['Point_Outcome'] == sel_point]

finish_options = ["すべて"] + [f for f in df_s1['Finish_Type'].unique() if f != "その他"]
chosen_finish = st.sidebar.selectbox("■ 決まり方", finish_options)

if chosen_finish == "すべて":
    final_df = df_s1
else:
    final_df = df_s1[df_s1['Finish_Type'] == chosen_finish]

if final_df.empty:
    st.warning("⚠️ 選択した条件に一致するポイントがありません。")
    st.stop()

point_list = final_df['Point'].tolist()

filter_sig = f"{sel_point}_{chosen_finish}"
if "last_filter_sig" not in st.session_state or st.session_state.last_filter_sig != filter_sig:
    st.session_state.last_filter_sig = filter_sig
    st.session_state.cur_pt_idx = 0

if "cur_pt_idx" not in st.session_state or st.session_state.cur_pt_idx >= len(point_list):
    st.session_state.cur_pt_idx = 0

st.sidebar.markdown("---")
st.sidebar.header("🎨 表示設定")
view_mode = st.sidebar.radio("描画モード", ["全ラリー表示", "決着ラスト2打のみ表示"], index=0)

if "main_pt_select" not in st.session_state or st.session_state.main_pt_select not in point_list:
    st.session_state.main_pt_select = point_list[st.session_state.cur_pt_idx]

def go_prev_pt():
    if st.session_state.cur_pt_idx > 0:
        st.session_state.cur_pt_idx -= 1
        st.session_state.main_pt_select = point_list[st.session_state.cur_pt_idx]

def go_next_pt():
    if st.session_state.cur_pt_idx < len(point_list) - 1:
        st.session_state.cur_pt_idx += 1
        st.session_state.main_pt_select = point_list[st.session_state.cur_pt_idx]

def on_main_select():
    chosen = st.session_state.main_pt_select
    if chosen in point_list:
        st.session_state.cur_pt_idx = point_list.index(chosen)

# CSS: プルダウン幅を横長にせずコンパクトに固定
st.markdown("""
<style>
.block-container { padding-top: 3.5rem !important; padding-bottom: 1rem !important; }
[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }

/* ナビゲーションバーの固定 */
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 8px !important;
    width: 200px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(1),
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(3) {
    flex: 0 0 44px !important;
    width: 44px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(2) {
    flex: 0 0 90px !important;
    width: 90px !important;
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
    st.button("◀", key="main_prev", on_click=go_prev_pt, use_container_width=True)
with col_sel:
    st.selectbox("Point #", options=point_list, key="main_pt_select", on_change=on_main_select, label_visibility="collapsed")
with col_next:
    st.button("▶", key="main_next", on_click=go_next_pt, use_container_width=True)

selected_point = point_list[st.session_state.cur_pt_idx]
p_info = full_meta_df[full_meta_df['Point'] == selected_point].iloc[0]
p_shots = shots_dict.get(selected_point, pd.DataFrame())

col_court, col_info = st.columns([1.1, 1.0])

# ====================================================
# 【左側】コート描画
# ====================================================
with col_court:
    NET_Y = 11.885
    focal_shots = p_shots[p_shots['Player'] == target_player]
    is_far = False
    if not focal_shots.empty and focal_shots['Hit (y)'].mean() > NET_Y:
        is_far = True

    records = []
    for idx, row in p_shots.iterrows():
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

    color_focal = '#38bdf8'
    color_opp = '#fb923c'
    color_net_miss = '#ef4444'

    for i, cur in enumerate(records):
        c = color_focal if cur['player'] == target_player else color_opp
        is_net = (cur['result'] == 'NET')
        target_x, target_y = cur['bx'], cur['by']
        annotation_c = c
        speed_color = get_speed_color(cur.get('speed', 0))

        if is_net:
            hx, hy = cur['hx'], cur['hy']
            bx, by = cur['bx'], cur['by']
            target_y = NET_Y
            if hy != by:
                target_x = hx + (bx - hx) * (NET_Y - hy) / (by - hy)
            annotation_c = color_net_miss

        ls_arrow = '-' if (cur['result'] == 'IN' or is_net) else '--'
        ax.annotate(
            '', xy=(target_x, target_y), xytext=(cur['hx'], cur['hy']),
            arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.5",
                            color=speed_color, lw=2.5, alpha=0.95, linestyle=ls_arrow)
        )

        if cur['shot'] == 1:
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=13, color='#eab308', markeredgecolor='#ffffff', markeredgewidth=2, zorder=5)
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, zorder=6)
            ax.text(cur['hx'], cur['hy'] - 0.7 if cur['hy'] < NET_Y else cur['hy'] + 0.7,
                    '★SERVE', color='#fde047', fontsize=8, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#000000', edgecolor='#fde047', alpha=0.85))
        else:
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, markeredgecolor='#ffffff', markeredgewidth=1, zorder=4)

        if is_net:
            ax.plot(target_x, target_y, marker='X', markersize=16, color=color_net_miss, markeredgecolor='#ffffff', markeredgewidth=2, zorder=11)
        else:
            b_marker = '*' if cur['result'] == 'IN' else 'x'
            ax.plot(target_x, target_y, marker=b_marker, markersize=11, color=annotation_c, markeredgecolor='#ffffff', markeredgewidth=1.5, zorder=4)

        if i + 1 < len(records) and not is_net:
            nxt = records[i+1]
            ax.annotate(
                '', xy=(nxt['hx'], nxt['hy']), xytext=(cur['bx'], cur['by']),
                arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.4",
                                color=c, lw=1.5, alpha=0.6, linestyle=':')
            )

        offset_y = 0.55 if cur['hy'] < target_y else -0.55
        label_c = annotation_c if is_net else '#ffffff'
        bbox_c = color_net_miss if is_net else '#1e293b'

        player_tag = "Me" if cur['player'] == target_player else "Opponent"
        label_text = f"#{cur['shot']} {player_tag}\n{cur['stroke']} ({cur['speed']:.0f}km/h)"
        if is_net:
            label_text += "\n[NET]"
        elif cur['result'] == 'OUT':
            label_text += "\n[OUT]"

        ax.text(target_x, target_y + offset_y, label_text, color=label_c, fontsize=7.5,
                ha='center', va='center', zorder=7,
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#0f172a', edgecolor=bbox_c, alpha=0.9))

    near_label = f"NEAR: {target_player}"
    ax.text(0, -2.0, near_label, color='#38bdf8', fontsize=11, fontweight='bold', ha='center', fontfamily=selected_font)
    ax.text(0, 25.2, "FAR: OPPONENT", color='#fb923c', fontsize=11, fontweight='bold', ha='center')

    ax.set_xlim(-6.8, 6.8)
    ax.set_ylim(-3.5, 27.2)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')

    st.pyplot(fig, use_container_width=True)

# ====================================================
# 【右側】概要 ＆ ショット詳細
# ====================================================
with col_info:
    st.write(f"**🎾 スコア:** {p_info['Score']}")
    st.write(f"**📌 Point {selected_point} 概要**")
    st.write(f"**ポイント勝敗:** {p_info['Point_Outcome']}")
    st.write(f"**ラリー打数:** {p_info['Total_Shots']} 打 ｜ **決まり方:** {p_info['Finish_Type']}")
    st.write(f"**決着展開:** {p_info['Detail']}")

    st.write("---")
    st.write("**ショット詳細**")
    if not p_shots.empty:
        display_df = p_shots.copy()
        display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
        display_df['Result'] = display_df['Result'].apply(translate_result)
        display_df['Shot_No'] = display_df.get('Shot_Display', display_df['Shot'])

        cols_to_show = ['Shot_No', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
        st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("このポイントに対応するショット詳細がありません。")
