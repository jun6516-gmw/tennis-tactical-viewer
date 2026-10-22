import streamlit as st
import pandas as pd
import numpy as np
import io
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
    <style>
    /* PC表示（769px以上）：PC用テキストを表示し、スマホ用を非表示 */
    .msg-pc { display: inline !important; }
    .msg-sp { display: none !important; }

    /* スマホ表示（768px以下）：スマホ用テキストを表示し、PC用を非表示 */
    @media (max-width: 768px) {
        .msg-pc { display: none !important; }
        .msg-sp { display: inline !important; }
    }
    </style>
    <div style="background-color: #f0f7ff; color: #1e3a8a; padding: 14px 16px; border-radius: 8px; border-left: 5px solid #2563eb; margin: 10px 0;">
        <span class="msg-pc">👈 <strong>左側のサイドバーから</strong></span>
        <span class="msg-sp">👆 <strong>上の >> をクリックして</strong></span>
        SwingVision のデータファイル（Excel または CSV）をアップロードしてください。
    </div>
    """, unsafe_allow_html=True)
    st.stop()
# ----------------------------------------------------
# 1. 生ファイルの読み込み（キャッシュ化）
# ----------------------------------------------------
@st.cache_data
def load_raw_data(file_bytes, file_name):
    shots = pd.DataFrame()
    points = pd.DataFrame()

    if file_name.endswith(".xlsx"):
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        if "Shots" in xls.sheet_names:
            shots = pd.read_excel(xls, sheet_name="Shots")
        else:
            shots = pd.read_excel(xls, sheet_name=0)
            
        if "Points" in xls.sheet_names:
            points = pd.read_excel(xls, sheet_name="Points")
    else:
        shots = pd.read_csv(io.BytesIO(file_bytes))

    return shots, points

raw_bytes = uploaded_file.getvalue()
try:
    shots_raw, points_raw = load_raw_data(raw_bytes, uploaded_file.name)
except Exception as e:
    st.error(f"ファイルの読み込みに失敗しました: {e}")
    st.stop()

if shots_raw.empty:
    st.error("Shotsデータが存在しません。")
    st.stop()

players = [p for p in shots_raw['Player'].dropna().unique().tolist() if str(p).strip()]
if not players:
    st.error("有効なPlayerデータが存在しません。")
    st.stop()

st.sidebar.header("👤 プレイヤー視点設定")
target_player = st.sidebar.selectbox("手前側に固定するプレイヤーを選択", players, index=0)

# ----------------------------------------------------
# 2. 自動前処理・加工エンジン（初回のみ実行＆キャッシュ）
# ----------------------------------------------------
PT_MAP = {0: "0", 1: "15", 2: "30", 3: "40"}

@st.cache_data
def process_and_cache_dataset(shots, points, focus_player):
    dataset = []

    # A. Pointsシートがありデータ行も入っている場合
    if not points.empty and len(points) > 0 and 'Video Time' in points.columns:
        scene_counter = 1
        for idx, pt_row in points.iterrows():
            orig_p_id = int(pt_row['Point'])
            end_t = float(pt_row['Video Time'])
            dur = float(pt_row.get('Duration', 0.0))
            start_t = max(0.0, end_t - dur - 1.2) if dur > 0 else max(0.0, end_t - 8.0)

            sub_shots = shots[(shots['Video Time'] >= start_t) & (shots['Video Time'] <= end_t + 1.2)].copy()
            if sub_shots.empty:
                sub_shots = shots[shots['Point'] == orig_p_id].copy()

            sub_shots = sub_shots.sort_values('Video Time')
            sub_shots['Shot_Display'] = range(1, len(sub_shots) + 1)

            h_score = str(pt_row.get('Host Game Score', '0'))
            g_score = str(pt_row.get('Guest Game Score', '0'))
            game_num = pt_row.get('Game', 1)
            set_num = pt_row.get('Set', 1)
            score_str = f"Set {set_num} | Game {game_num} ({h_score}-{g_score})"

            winner = str(pt_row.get('Point Winner', ''))
            detail = str(pt_row.get('Detail', ''))

            is_1st_fault = False
            if len(sub_shots) == 1:
                first_s = sub_shots.iloc[0]
                if 'first_serve' in str(first_s.get('Type', '')) and first_s['Result'] in ['ネット', 'アウト']:
                    is_1st_fault = True

            if is_1st_fault:
                point_outcome = "-"
                finish_type = "1st Fault"
            else:
                point_outcome = "取った" if winner == focus_player else "落とした"
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
                'Scene': scene_counter,
                'Orig_Point': orig_p_id,
                'Score': score_str,
                'Point_Outcome': point_outcome,
                'Finish_Type': finish_type,
                'Total_Shots': len(sub_shots),
                'Detail': detail if detail else f"Winner: {winner}",
                'Shots_DF': sub_shots
            })
            scene_counter += 1

    # B. Pointsシートが無い場合のフォールバック（Shotsシートから通しシミュレーション）
    else:
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
                'Orig_Point': int(p_id),
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
        scene_counter = 1

        for idx, item in enumerate(temp_scenes):
            grp = item['Shots']
            first_s = grp.iloc[0]
            server = str(first_s['Player'])

            is_1st_fault = (len(grp) == 1 and 'first_serve' in str(first_s.get('Type', '')) and first_s['Result'] in ['ネット', 'アウト'])

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

            is_tb = (g_w == 6 and g_l == 6)
            if not is_1st_fault and not is_let and not is_tb:
                will_game_end = False
                if item['Won'] and p_w >= 3 and (p_w + 1 - p_l >= 2):
                    will_game_end = True
                elif not item['Won'] and p_l >= 3 and (p_l + 1 - p_w >= 2):
                    will_game_end = True

                if will_game_end and idx + 1 < len(temp_scenes):
                    next_grp = temp_scenes[idx + 1]['Shots']
                    if not next_grp.empty and str(next_grp.iloc[0]['Player']) == server:
                        is_let = True

            if is_let:
                continue

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
            if not is_1st_fault:
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
            grp_copy['Shot_Display'] = range(1, len(grp_copy) + 1)

            final_outcome = "-" if is_1st_fault else item['Outcome']
            final_finish = "1st Fault" if is_1st_fault else item['Finish']

            dataset.append({
                'Scene': scene_counter,
                'Orig_Point': item['Orig_Point'],
                'Score': score_text,
                'Point_Outcome': final_outcome,
                'Finish_Type': final_finish,
                'Total_Shots': len(grp),
                'Detail': item['Detail'],
                'Shots_DF': grp_copy
            })
            scene_counter += 1

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

# 前処理の実行（初回のみ）
with st.spinner("試合データを解析・最適化中..."):
    match_scenes = process_and_cache_dataset(shots_raw, points_raw, target_player)

if not match_scenes:
    st.error("有効なシーンデータが見つかりませんでした。")
    st.stop()

full_meta_df = pd.DataFrame([{k: v for k, v in item.items() if k != 'Shots_DF'} for item in match_scenes])
shots_dict = {item['Scene']: item['Shots_DF'] for item in match_scenes}

# ----------------------------------------------------
# サイドバー: フィルタ ＆ ダウンロード
# ----------------------------------------------------
st.sidebar.header("🔍 フィルタ設定")

c_all = len(full_meta_df)
c_won = len(full_meta_df[full_meta_df['Point_Outcome'] == '取った'])
c_lost = len(full_meta_df[full_meta_df['Point_Outcome'] == '落とした'])
c_none = len(full_meta_df[full_meta_df['Point_Outcome'] == '-'])

outcome_map = {
    f"すべて ({c_all})": "すべて",
    f"取った ({c_won})": "取った",
    f"落とした ({c_lost})": "落とした"
}
if c_none > 0:
    outcome_map[f"- / 1st Fault ({c_none})"] = "-"

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
st.sidebar.header("📥 データ出力")
csv_buffer = io.StringIO()
full_meta_df.to_csv(csv_buffer, index=False)
st.sidebar.download_button(
    label="加工済みScene一覧(CSV)を保存",
    data=csv_buffer.getvalue().encode('utf-8-sig'),
    file_name="processed_scenes.csv",
    mime="text/csv"
)

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

# ----------------------------------------------------
# CSS: スマホ時のコート縮小 ＆ ナビゲーションの固定
# ----------------------------------------------------
st.markdown("""
<style>
.block-container { padding-top: 3.5rem !important; padding-bottom: 1rem !important; }
[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }

/* ナビゲーションバー：折り返し防止とボタンサイズの統一 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    width: 100% !important;
}

div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 42px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

/* 中央の Scene プルダウンの枠幅（残りを自動で埋める設定） */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div:nth-child(2) {
    flex: 1 1 auto !important;
    max-width: 200px !important;
}

/* ボタンの高さ */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 38px !important;
    width: 100% !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

/* プルダウン内部の文字余白を調整し、文字隠れを防止 */
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-baseweb="select"] {
    font-size: 14px !important;
}
div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-baseweb="select"] > div {
    padding-left: 8px !important;
    padding-right: 4px !important;
}

div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 38px !important;
    width: 100% !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

/* スマホ表示時（768px以下）：コート画像を中央寄せで適度な大きさに縮小 */
@media (max-width: 768px) {
    div[data-testid="stImage"],
    div[data-testid="stpyplot"],
    div[data-testid="stPlotlyChart"],
    div.element-container:has(figure) {
        width: 68% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ナビゲーションUI（左右のボタンを小さく、中央を主役に配置）
col_prev, col_sel, col_next = st.columns([0.6, 2.2, 0.6], gap="small")
with col_prev:
    st.button("◀", key="main_prev", on_click=go_prev_scene, use_container_width=True)
with col_sel:
    st.selectbox("Scene #", options=scene_list, key="main_scene_select", on_change=on_main_select, label_visibility="collapsed")
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
    opp_shots = s_shots[s_shots['Player'] != target_player]
    
    # 手前・奥の判定（相手のみのフォールト時も正確に判定）
    is_far = False
    if not focal_shots.empty:
        if focal_shots['Hit (y)'].mean() > NET_Y:
            is_far = True
    elif not opp_shots.empty:
        if opp_shots['Hit (y)'].mean() < NET_Y:
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
    st.write(f"**🎾 スコア:** {s_info['Score']}")
    st.write(f"**📌 概要**")
    st.write(f"**勝敗:** {s_info['Point_Outcome']}")
    st.write(f"**ラリー打数:** {s_info['Total_Shots']} 打 ｜ **決まり方:** {s_info['Finish_Type']}")
    st.write(f"**決着展開:** {s_info['Detail']}")

    st.write("---")
    st.write("**ショット詳細**")
    if not s_shots.empty:
        display_df = s_shots.copy()
        display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
        display_df['Result'] = display_df['Result'].apply(translate_result)
        display_df['Shot_No'] = display_df.get('Shot_Display', display_df['Shot'])

        cols_to_show = ['Shot_No', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
        st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("このシーンに対応するショット詳細がありません。")
