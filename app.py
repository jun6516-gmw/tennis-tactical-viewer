import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors

# ----------------------------------------------------
# 打球速度に応じたカラーマップの定義
# 0km/h: 白 -> 60km/h: 緑 -> 100km/h: 黄 -> 150km/h以上: 赤
# ----------------------------------------------------
speed_thresholds = [0, 60, 100, 150]
colors_list = ["#ffffff", "#22c55e", "#eab308", "#ef4444"]

positions = [s / 150.0 for s in speed_thresholds]
cmap_dict = list(zip(positions, colors_list))
ball_speed_cmap = mcolors.LinearSegmentedColormap.from_list("ball_speed_cmap", cmap_dict)

def get_speed_color(speed_kmh):
    """打球速度(km/h)から無段階のグラデーション色(HEX)を返す"""
    if speed_kmh is None or np.isnan(speed_kmh) or speed_kmh <= 0:
        return "#ffffff"
    norm_val = np.clip(speed_kmh / 150.0, 0.0, 1.0)
    return mcolors.to_hex(ball_speed_cmap(norm_val))

# OS依存のないフォント設定
JP_FONTS = [
    'Yu Gothic', 'Meiryo', 'MS Gothic',
    'Hiragino Sans', 'Hiragino Kaku Gothic ProN',
    'Noto Sans CJK JP', 'TakaoGothic', 'IPAGothic', 'DejaVu Sans'
]
available_fonts = {f.name for f in fm.fontManager.ttflist}
for font in JP_FONTS:
    if font in available_fonts:
        plt.rcParams['font.family'] = font
        break

# ページ基本設定
st.set_page_config(page_title="Tennis Match Tactical Visualizer", layout="wide")

STROKE_MAP = {
    'サーブ': 'Serve',
    'フォアハンド': 'Forehand',
    'バックハンド': 'Backhand',
    'フォアハンド ボレー': 'FH Volley',
    'バックハンド ボレー': 'BH Volley',
    'スマッシュ': 'Smash',
    'ドロップ': 'Drop Shot',
    'フィード': 'Feed'
}

RESULT_MAP = {
    'イン': 'IN',
    'アウト': 'OUT',
    'ネット': 'NET'
}

def translate_stroke(stroke):
    return STROKE_MAP.get(str(stroke), str(stroke))

def translate_result(result):
    return RESULT_MAP.get(str(result), str(result))

# サイドバー: ファイル読み込み
st.sidebar.header("📁 データ読み込み")
uploaded_file = st.sidebar.file_uploader("SwingVisionファイルを選択 (.xlsx / .csv)", type=["xlsx", "csv"])

if uploaded_file is None:
    st.markdown("""
    <style>
    .msg-pc { display: none !important; }
    .msg-sp { display: inline !important; }
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .msg-pc { display: inline !important; }
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .msg-sp { display: none !important; }
    </style>
    <div style="background-color: #f0f7ff; color: #1e3a8a; padding: 14px 16px; border-radius: 8px; border-left: 5px solid #2563eb; margin: 10px 0;">
        <span class="msg-pc">👈 <strong>左側のサイドバーから</strong></span>
        <span class="msg-sp">👆 <strong>上の >> をクリックして</strong></span>
        SwingVision のデータファイル（Excel または CSV）をアップロードしてください。
    </div>
    """, unsafe_allow_html=True)
    st.stop()

@st.cache_data
def load_all_sheets(file):
    shots = pd.DataFrame()
    points = pd.DataFrame()
    games = pd.DataFrame()
    settings = pd.DataFrame()

    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        if "Shots" in xls.sheet_names:
            shots = pd.read_excel(xls, sheet_name="Shots")
        else:
            shots = pd.read_excel(xls, sheet_name=0)
            
        if "Points" in xls.sheet_names:
            points = pd.read_excel(xls, sheet_name="Points")
        if "Games" in xls.sheet_names:
            games = pd.read_excel(xls, sheet_name="Games")
        if "Settings" in xls.sheet_names:
            settings = pd.read_excel(xls, sheet_name="Settings")
    else:
        shots = pd.read_csv(file)

    return shots, points, games, settings

try:
    shots_df, points_df, games_df, settings_df = load_all_sheets(uploaded_file)
except Exception as e:
    st.error(f"ファイルの読み込みに失敗しました: {e}")
    st.stop()

if shots_df.empty:
    st.error("Shotsデータが存在しません。")
    st.stop()

# プレイヤー一覧取得
players = [p for p in shots_df['Player'].dropna().unique().tolist() if str(p).strip()]
if not players:
    st.error("Playerデータが存在しません。")
    st.stop()

st.sidebar.header("👤 プレイヤー視点設定")
target_player = st.sidebar.selectbox("手前側に固定するプレイヤーを選択", players, index=0)

# ----------------------------------------------------
# PointsシートとShotsシートの統合処理
# ----------------------------------------------------
@st.cache_data
def build_match_points_dataset(shots, points, focus_player):
    dataset = []

    # A. Pointsシートが存在し、かつデータがある場合（公式スコア連携モード）
    if not points.empty and 'Video Time' in points.columns and 'Duration' in points.columns:
        for idx, pt_row in points.iterrows():
            pt_id = int(pt_row['Point'])
            end_t = float(pt_row['Video Time'])
            dur = float(pt_row['Duration'])
            start_t = max(0.0, end_t - dur - 1.2)  # マージン1.2秒
            
            # 該当する打球をShotsシートから時間範囲で抽出
            sub_shots = shots[(shots['Video Time'] >= start_t) & (shots['Video Time'] <= end_t + 1.2)].copy()
            
            if sub_shots.empty:
                # 時間で取れない場合はPoint列でフォールバック
                sub_shots = shots[shots['Point'] == pt_id].copy()
                
            sub_shots = sub_shots.sort_values('Video Time')
            
            # 打球番号の再採番（1, 2, 3...）
            sub_shots['Shot_Display'] = range(1, len(sub_shots) + 1)
            
            # スコア文字列の生成
            h_score = str(pt_row.get('Host Game Score', '0'))
            g_score = str(pt_row.get('Guest Game Score', '0'))
            game_num = pt_row.get('Game', 1)
            set_num = pt_row.get('Set', 1)
            score_str = f"Set {set_num} | Game {game_num} ({h_score}-{g_score})"
            
            winner = str(pt_row.get('Point Winner', ''))
            if winner:
                point_outcome = "取った" if winner == focus_player else "落とした"
            else:
                point_outcome = "不明"

            detail = str(pt_row.get('Detail', ''))
            
            # 決まり方の判定
            finish_type = "その他"
            if "アウト" in detail or "out" in detail.lower():
                finish_type = "アウト"
            elif "ネット" in detail or "net" in detail.lower():
                finish_type = "ネット"
            elif "エース" in detail or "ace" in detail.lower():
                finish_type = "エース"
            elif "ウィナー" in detail or "winner" in detail.lower():
                finish_type = "ウィナー"

            # キーショット判定
            key_cat, key_typ, key_crs = "なし", "なし", "なし"
            if not sub_shots.empty:
                last_shot = sub_shots.iloc[-1]
                prev_shot = sub_shots.iloc[-2] if len(sub_shots) >= 2 else None
                
                key_row = None
                if point_outcome == "取った":
                    if finish_type in ["エース", "ウィナー"] and str(last_shot['Player']) == focus_player:
                        key_row = last_shot
                    elif prev_shot is not None and str(prev_shot['Player']) == focus_player:
                        key_row = prev_shot
                else:
                    if str(last_shot['Player']) == focus_player and finish_type in ["アウト", "ネット"]:
                        key_row = last_shot
                    elif prev_shot is not None and str(prev_shot['Player']) == focus_player:
                        key_row = prev_shot

                if key_row is not None:
                    stk = str(key_row.get('Stroke', ''))
                    dir_val = str(key_row.get('Direction', ''))
                    stk_c = stk.lower().strip()
                    dir_c = dir_val.lower().strip()

                    crs = "その他"
                    if 'クロス' in dir_val or 'cross' in dir_c:
                        crs = "クロス"
                    elif '逆クロス' in dir_val or 'inside' in dir_c or 'ストレート' in dir_val or 'line' in dir_c:
                        crs = "逆クロス"

                    if 'サーブ' in stk or 'serve' in stk_c:
                        key_cat = "サービス"
                        key_crs = "センター" if ('センター' in dir_val or 'center' in dir_c or ' t' in dir_c) else ("ワイド" if 'ワイド' in dir_val else "その他")
                    elif 'ボレー' in stk or 'volley' in stk_c:
                        key_cat = "ボレー"
                        key_typ = "フォア" if ('フォア' in stk or 'fh' in stk_c) else "バック"
                        key_crs = crs
                    elif 'スマッシュ' in stk or 'smash' in stk_c:
                        key_cat = "スマッシュ"
                        key_crs = crs
                    else:
                        key_cat = "グラウンドストローク"
                        key_typ = "フォア" if ('フォア' in stk or 'fh' in stk_c) else "バック"
                        key_crs = crs

            dataset.append({
                'Point': pt_id,
                'Score': score_str,
                'Point_Outcome': point_outcome,
                'Finish_Type': finish_type,
                'Total_Shots': len(sub_shots),
                'Detail': detail if detail else f"Winner: {winner}",
                'Key_Category': key_cat,
                'Key_Type': key_typ,
                'Key_Course': key_crs,
                'Shots_DF': sub_shots
            })

    # B. Pointsシートが無い場合のフォールバック（Shotsシートから直接集計）
    else:
        valid_p_ids = []
        for p_id, grp in shots.groupby('Point'):
            f_row = grp.sort_values('Shot').iloc[0]
            if f_row['Shot'] == 1 and 'サーブ' in str(f_row['Stroke']):
                valid_p_ids.append(p_id)
                
        shots_clean = shots[shots['Point'].isin(valid_p_ids)].copy()
        for p_id in sorted(valid_p_ids):
            grp = shots_clean[shots_clean['Point'] == p_id].sort_values('Shot').copy()
            grp['Shot_Display'] = grp['Shot']
            last_shot = grp.iloc[-1]
            last_p = str(last_shot['Player'])
            last_res = translate_result(last_shot['Result'])
            
            p_won = (last_p == focus_player and last_res == "IN") or (last_p != focus_player and last_res in ["OUT", "NET"])
            dataset.append({
                'Point': int(p_id),
                'Score': f"Point #{p_id}",
                'Point_Outcome': "取った" if p_won else "落とした",
                'Finish_Type': "アウト" if last_res == "OUT" else ("ネット" if last_res == "NET" else "エース"),
                'Total_Shots': len(grp),
                'Detail': f"{last_p}: {translate_stroke(last_shot['Stroke'])} -> {last_res}",
                'Key_Category': "なし",
                'Key_Type': "なし",
                'Key_Course': "なし",
                'Shots_DF': grp
            })

    return dataset

match_points = build_match_points_dataset(shots_df, points_df, target_player)

if not match_points:
    st.error("有効なポイントデータが見つかりませんでした。")
    st.stop()

full_meta_df = pd.DataFrame([{k: v for k, v in item.items() if k != 'Shots_DF'} for item in match_points])
shots_dict = {item['Point']: item['Shots_DF'] for item in match_points}

# ----------------------------------------------------
# サイドバー: フィルタUI
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

cnt_s1 = len(df_s1)

finish_options = ["すべて"] + [f for f in df_s1['Finish_Type'].unique() if f != "その他"]
chosen_finish = st.sidebar.selectbox("■ 決まり方", finish_options)

if chosen_finish == "すべて":
    final_df = df_s1
else:
    final_df = df_s1[df_s1['Finish_Type'] == chosen_finish]

if final_df.empty:
    st.warning("⚠️ 選択した条件に一致するポイントがありません。フィルタ条件を緩和してください。")
    st.stop()

point_list = final_df['Point'].tolist()

# 状態管理
filter_sig = f"{sel_point}_{chosen_finish}"
if "last_filter_sig" not in st.session_state or st.session_state.last_filter_sig != filter_sig:
    st.session_state.last_filter_sig = filter_sig
    st.session_state.cur_pt_idx = 0

if "cur_pt_idx" not in st.session_state or st.session_state.cur_pt_idx >= len(point_list):
    st.session_state.cur_pt_idx = 0

# 表示設定
st.sidebar.markdown("---")
st.sidebar.header("🎨 表示設定")
view_mode = st.sidebar.radio("描画モード", ["全ラリー表示", "決着ラスト2打のみ表示"], index=0)

# ナビゲーション関数
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

# CSSスタイル
st.markdown("""
<style>
.block-container { padding-top: 3.5rem !important; padding-bottom: 1rem !important; }
[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
    align-items: center !important; gap: 6px !important; margin-bottom: -12px !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 40px !important; font-size: 16px !important; font-weight: bold !important;
}
@media (max-width: 768px) {
    [data-testid="stPlotlyChart"], div.element-container:has(figure) {
        width: 75% !important; margin-left: auto !important; margin-right: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ナビゲーションUI
col_prev, col_sel, col_next = st.columns([1, 6, 1])
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

    ax.text(0, -2.0, f"NEAR: {target_player}", color='#38bdf8', fontsize=12, fontweight='bold', ha='center')
    ax.text(0, 25.2, "FAR: OPPONENT", color='#fb923c', fontsize=12, fontweight='bold', ha='center')

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
    if p_info.get('Key_Category', 'なし') != 'なし':
        st.write(f"**手前のキーショット:** {p_info['Key_Category']} ({p_info['Key_Type']} / {p_info['Key_Course']})")

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
