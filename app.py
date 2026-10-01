import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm

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

# ページ基本設定（タイトルテキスト類はスマホ画面を最大活用するため全撤去）
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
    st.info("👈 左側のサイドバーから SwingVision のデータファイル（Excel または CSV）をアップロードしてください。")
    st.stop()

@st.cache_data
def load_data(file):
    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        if "Shots" in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name="Shots")
        else:
            df = pd.read_excel(xls, sheet_name=0)
    else:
        df = pd.read_csv(file)
    return df

try:
    shots_df = load_data(uploaded_file)
except Exception as e:
    st.error(f"ファイルの読み込みに失敗しました: {e}")
    st.stop()

required_cols = ['Point', 'Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Bounce (x)', 'Bounce (y)', 'Hit (x)', 'Hit (y)', 'Result']
missing_cols = [c for c in required_cols if c not in shots_df.columns]
if missing_cols:
    st.error(f"必要なカラムが見つかりません: {missing_cols}")
    st.stop()

players = [p for p in shots_df['Player'].dropna().unique().tolist() if str(p).strip()]
if not players:
    st.error("Playerデータが存在しません。")
    st.stop()

st.sidebar.header("👤 プレイヤー視点設定")
target_player = st.sidebar.selectbox("手前側に固定するプレイヤーを選択", players, index=0)

# ポイントサマリー & 手前選手のキーショット特定
@st.cache_data
def analyze_points_and_keyshots(df, focus_player):
    points_data = []
    grouped = df.groupby('Point')
    
    for point_id, group in grouped:
        group_sorted = group.sort_values('Shot')
        last_shot = group_sorted.iloc[-1]
        
        last_player = str(last_shot['Player'])
        last_stroke = translate_stroke(last_shot['Stroke'])
        last_res = translate_result(last_shot['Result'])
        total_shots = len(group_sorted)
        
        # ポイント勝敗
        if last_player == focus_player:
            point_outcome = "取った" if last_res == "IN" else "落とした"
        else:
            point_outcome = "取った" if last_res in ["OUT", "NET"] else "落とした"
            
        # 決まり方
        if last_res == "OUT":
            finish_type = "アウト"
        elif last_res == "NET":
            finish_type = "ネット"
        elif last_res == "IN":
            finish_type = "エース"
        else:
            finish_type = "その他"
            
        # 手前選手のキーショット判定
        key_shot_row = None
        if point_outcome == "取った":
            if finish_type == "エース" and last_player == focus_player:
                key_shot_row = last_shot
            elif finish_type in ["アウト", "ネット"]:
                if len(group_sorted) >= 2:
                    prev_shot = group_sorted.iloc[-2]
                    if str(prev_shot['Player']) == focus_player:
                        key_shot_row = prev_shot
        else: # 落とした
            if finish_type == "エース":
                if len(group_sorted) >= 2:
                    prev_shot = group_sorted.iloc[-2]
                    if str(prev_shot['Player']) == focus_player:
                        key_shot_row = prev_shot
            elif finish_type in ["アウト", "ネット"] and last_player == focus_player:
                key_shot_row = last_shot

        # キーショットの分類情報
        shot_category = "なし"
        shot_type = "なし"
        shot_course = "なし"
        
        if key_shot_row is not None:
            stk = str(key_shot_row.get('Stroke', ''))
            dir_val = str(key_shot_row.get('Direction', ''))
            stk_clean = stk.lower().strip()
            dir_clean = dir_val.lower().strip()
            
            is_serve = ('サーブ' in stk or 'serve' in stk_clean)
            is_volley = ('ボレー' in stk or 'volley' in stk_clean)
            is_smash = ('スマッシュ' in stk or 'smash' in stk_clean)
            
            # コース判定共通
            course_val = "その他"
            if 'クロス' in dir_val or 'cross' in dir_clean:
                course_val = "クロス"
            elif '逆クロス' in dir_val or 'inside' in dir_clean or 'ストレート' in dir_val or 'down the line' in dir_clean or 'line' in dir_clean:
                course_val = "逆クロス"

            if is_serve:
                shot_category = "サービス"
                if 'センター' in dir_val or 'center' in dir_clean or ' t' in dir_clean or dir_clean == 't':
                    shot_course = "センター"
                elif 'ワイド' in dir_val or 'wide' in dir_clean:
                    shot_course = "ワイド"
                else:
                    shot_course = "その他"
            elif is_volley:
                shot_category = "ボレー"
                shot_type = "フォア" if ('フォア' in stk or 'forehand' in stk_clean or stk_clean.startswith('fh')) else "バック"
                shot_course = course_val
            elif is_smash:
                shot_category = "スマッシュ"
                shot_course = course_val
            else:
                shot_category = "グラウンドストローク"
                shot_type = "フォア" if ('フォア' in stk or 'forehand' in stk_clean or stk_clean.startswith('fh')) else "バック"
                shot_course = course_val

        points_data.append({
            'Point': int(point_id),
            'Total_Shots': total_shots,
            'Point_Outcome': point_outcome,
            'Finish_Type': finish_type,
            'Last_Player': last_player,
            'Last_Stroke': last_stroke,
            'Last_Result': last_res,
            'Detail': f"{last_player}: {last_stroke} -> {last_res}",
            'Key_Category': shot_category,
            'Key_Type': shot_type,
            'Key_Course': shot_course
        })
    return pd.DataFrame(points_data)

full_meta_df = analyze_points_and_keyshots(shots_df, target_player)

# ----------------------------------------------------
# サイドバー: 段階連動型フィルタUI（キーショット基準）
# ----------------------------------------------------
st.sidebar.header("🔍 フィルタ設定")

# 1. ポイント
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

# 2. 決まり方
c_ace = len(df_s1[df_s1['Finish_Type'] == 'エース'])
c_out = len(df_s1[df_s1['Finish_Type'] == 'アウト'])
c_net = len(df_s1[df_s1['Finish_Type'] == 'ネット'])

finish_map = {
    f"すべて ({cnt_s1})": "すべて",
    f"エース ({c_ace})": "エース",
    f"アウト ({c_out})": "アウト",
    f"ネット ({c_net})": "ネット"
}
chosen_finish_label = st.sidebar.selectbox("■ 決まり方", list(finish_map.keys()))
sel_finish = finish_map[chosen_finish_label]

if sel_finish == "すべて":
    df_s2 = df_s1
else:
    df_s2 = df_s1[df_s1['Finish_Type'] == sel_finish]

cnt_s2 = len(df_s2)

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🎾 キーショットフィルタ")

# 3. サービス
df_srv = df_s2[df_s2['Key_Category'] == 'サービス']
c_srv_cen = len(df_srv[df_srv['Key_Course'] == 'センター'])
c_srv_wde = len(df_srv[df_srv['Key_Course'] == 'ワイド'])

serve_map = {
    f"すべて ({cnt_s2})": "すべて",
    f"センター ({c_srv_cen})": "センター",
    f"ワイド ({c_srv_wde})": "ワイド"
}
chosen_srv_label = st.sidebar.selectbox("サービス コース", list(serve_map.keys()))
sel_serve = serve_map[chosen_srv_label]

if sel_serve == "センター":
    df_s3 = df_s2[(df_s2['Key_Category'] == 'サービス') & (df_s2['Key_Course'] == 'センター')]
elif sel_serve == "ワイド":
    df_s3 = df_s2[(df_s2['Key_Category'] == 'サービス') & (df_s2['Key_Course'] == 'ワイド')]
else:
    df_s3 = df_s2

cnt_s3 = len(df_s3)

# 4. グラウンドストローク
df_gs = df_s3[df_s3['Key_Category'] == 'グラウンドストローク']
c_strk_fh = len(df_gs[df_gs['Key_Type'] == 'フォア'])
c_strk_bh = len(df_gs[df_gs['Key_Type'] == 'バック'])

gs_type_map = {
    f"すべて ({cnt_s3})": "すべて",
    f"フォア ({c_strk_fh})": "フォア",
    f"バック ({c_strk_bh})": "バック"
}
chosen_gs_type_label = st.sidebar.selectbox("ストローク タイプ", list(gs_type_map.keys()))
sel_gs_type = gs_type_map[chosen_gs_type_label]

# 4-2. ストローク コース
if sel_gs_type == "フォア":
    df_gs_sub = df_gs[df_gs['Key_Type'] == 'フォア']
elif sel_gs_type == "バック":
    df_gs_sub = df_gs[df_gs['Key_Type'] == 'バック']
else:
    df_gs_sub = df_gs

c_gs_cr = len(df_gs_sub[df_gs_sub['Key_Course'] == 'クロス'])
c_gs_in = len(df_gs_sub[df_gs_sub['Key_Course'] == '逆クロス'])
cnt_gs_sub = len(df_gs_sub)

gs_course_map = {
    f"すべて ({cnt_gs_sub})": "すべて",
    f"クロス ({c_gs_cr})": "クロス",
    f"逆クロス ({c_gs_in})": "逆クロス"
}
chosen_gs_course_label = st.sidebar.selectbox("ストローク コース", list(gs_course_map.keys()))
sel_gs_course = gs_course_map[chosen_gs_course_label]

# 5. ボレー
df_vol = df_s3[df_s3['Key_Category'] == 'ボレー']
c_vol_fh = len(df_vol[df_vol['Key_Type'] == 'フォア'])
c_vol_bh = len(df_vol[df_vol['Key_Type'] == 'バック'])

vol_type_map = {
    f"すべて ({cnt_s3})": "すべて",
    f"フォア ({c_vol_fh})": "フォア",
    f"バック ({c_vol_bh})": "バック"
}
chosen_vol_type_label = st.sidebar.selectbox("ボレー タイプ", list(vol_type_map.keys()))
sel_vol_type = vol_type_map[chosen_vol_type_label]

# 5-2. ボレー コース
if sel_vol_type == "フォア":
    df_vol_sub = df_vol[df_vol['Key_Type'] == 'フォア']
elif sel_vol_type == "バック":
    df_vol_sub = df_vol[df_vol['Key_Type'] == 'バック']
else:
    df_vol_sub = df_vol

c_vol_cr = len(df_vol_sub[df_vol_sub['Key_Course'] == 'クロス'])
c_vol_in = len(df_vol_sub[df_vol_sub['Key_Course'] == '逆クロス'])
cnt_vol_sub = len(df_vol_sub)

vol_course_map = {
    f"すべて ({cnt_vol_sub})": "すべて",
    f"クロス ({c_vol_cr})": "クロス",
    f"逆クロス ({c_vol_in})": "逆クロス"
}
chosen_vol_course_label = st.sidebar.selectbox("ボレー コース", list(vol_course_map.keys()))
sel_vol_course = vol_course_map[chosen_vol_course_label]

# 6. スマッシュ
df_sm = df_s3[df_s3['Key_Category'] == 'スマッシュ']
c_sm_cr = len(df_sm[df_sm['Key_Course'] == 'クロス'])
c_sm_in = len(df_sm[df_sm['Key_Course'] == '逆クロス'])
cnt_sm = len(df_sm)

smash_map = {
    f"すべて ({cnt_s3})": "すべて",
    f"クロス ({c_sm_cr})": "クロス",
    f"逆クロス ({c_sm_in})": "逆クロス"
}
chosen_smash_label = st.sidebar.selectbox("スマッシュ コース", list(smash_map.keys()))
sel_smash = smash_map[chosen_smash_label]

# ----------------------------------------------------
# 最終絞り込み処理
# ----------------------------------------------------
final_df = df_s3.copy()

if sel_gs_type != "すべて" or sel_gs_course != "すべて":
    final_df = final_df[final_df['Key_Category'] == 'グラウンドストローク']
    if sel_gs_type != "すべて":
        final_df = final_df[final_df['Key_Type'] == sel_gs_type]
    if sel_gs_course != "すべて":
        final_df = final_df[final_df['Key_Course'] == sel_gs_course]

if sel_vol_type != "すべて" or sel_vol_course != "すべて":
    final_df = final_df[final_df['Key_Category'] == 'ボレー']
    if sel_vol_type != "すべて":
        final_df = final_df[final_df['Key_Type'] == sel_vol_type]
    if sel_vol_course != "すべて":
        final_df = final_df[final_df['Key_Course'] == sel_vol_course]

if sel_smash != "すべて":
    final_df = final_df[final_df['Key_Category'] == 'スマッシュ']
    final_df = final_df[final_df['Key_Course'] == sel_smash]

if final_df.empty:
    st.warning("⚠️ 選択した条件に一致するポイントがありません。フィルタ条件を緩和してください。")
    st.stop()

point_list = final_df['Point'].tolist()

# ----------------------------------------------------
# ポイント選択状態の管理
# ----------------------------------------------------
filter_signature = f"{sel_point}_{sel_finish}_{sel_serve}_{sel_gs_type}_{sel_gs_course}_{sel_vol_type}_{sel_vol_course}_{sel_smash}"
if "last_filter_signature" not in st.session_state or st.session_state.last_filter_signature != filter_signature:
    st.session_state.last_filter_signature = filter_signature
    st.session_state.current_point_idx = 0

if "current_point_idx" not in st.session_state or st.session_state.current_point_idx >= len(point_list):
    st.session_state.current_point_idx = 0

# 表示モード切り替えはサイドバーに配置
st.sidebar.markdown("---")
st.sidebar.header("🎨 表示設定")
view_mode = st.sidebar.radio(
    "描画モード",
    ["全ラリー表示", "決着ラスト2打のみ表示"],
    index=0
)

# ----------------------------------------------------
# 【メイン画面】最優先：ナビゲーション ＆ コート表示
# ----------------------------------------------------
selected_point = point_list[st.session_state.current_point_idx]
p_shots = shots_df[shots_df['Point'] == selected_point].sort_values('Shot').copy()
p_info = full_meta_df[full_meta_df['Point'] == selected_point].iloc[0]

# ----------------------------------------------------
# スマホでも絶対に1行を維持する強制横並びスタイル
# ----------------------------------------------------
st.markdown("""
<style>
/* 操作バー専用の横並びコンテナ設定 */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 6px !important;
}

/* スマホ幅でも各カラムの幅を維持（縦積みを無効化） */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex: 1 1 0px !important;
    min-width: 0 !important;
}

/* 中央のセレクトボックスを少し広くする */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
    flex: 1.8 1 0px !important;
}

/* ボタンの余白と高さを統一してタップしやすく調整 */
div[data-testid="stButton"] button {
    height: 42px !important;
    padding: 0px 4px !important;
    font-size: 13px !important;
    font-weight: bold !important;
    white-space: nowrap !important;
}

/* セレクトボックスの高さも揃える */
div[data-baseweb="select"] {
    min-height: 42px !important;
    height: 42px !important;
}
div[data-baseweb="select"] > div {
    min-height: 42px !important;
    height: 42px !important;
    padding-top: 0px !important;
    padding-bottom: 0px !important;
}
</style>
""", unsafe_allow_html=True)

# ナビゲーション操作バー（◀ 前へ ｜ Point選択 ｜ 次へ ▶）
nav_c1, nav_c2, nav_c3 = st.columns([1, 1.8, 1])

with nav_c1:
    if st.button("◀ 前へ", use_container_width=True, key="main_prev"):
        if st.session_state.current_point_idx > 0:
            st.session_state.current_point_idx -= 1
            st.rerun()

with nav_c2:
    def on_main_select():
        chosen = st.session_state.main_pt_select
        if chosen in point_list:
            st.session_state.current_point_idx = point_list.index(chosen)
    
    st.selectbox(
        "Point #",
        options=point_list,
        index=st.session_state.current_point_idx,
        key="main_pt_select",
        on_change=on_main_select,
        label_visibility="collapsed"
    )

with nav_c3:
    if st.button("次へ ▶", use_container_width=True, key="main_next"):
        if st.session_state.current_point_idx < len(point_list) - 1:
            st.session_state.current_point_idx += 1
            st.rerun()

st.caption(f"該当: **{st.session_state.current_point_idx + 1} / {len(point_list)}** 件 (Point #{selected_point})")

# コート描画処理
NET_Y = 11.885
focal_shots = p_shots[p_shots['Player'] == target_player]
is_far = False
if not focal_shots.empty:
    if focal_shots['Hit (y)'].mean() > NET_Y:
        is_far = True
        
records = []
for idx, row in p_shots.iterrows():
    s_num = int(row['Shot'])
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

# コート描画
rect_court = patches.Rectangle((-5.485, 0), 10.97, 23.77, linewidth=2, edgecolor='#64748b', facecolor='#1e3a8a', alpha=0.9)
ax.add_patch(rect_court)
rect_singles = patches.Rectangle((-4.115, 0), 8.23, 23.77, linewidth=1.5, edgecolor='#cbd5e1', facecolor='none')
ax.add_patch(rect_singles)

# ネット線
ax.plot([-5.8, 5.8], [NET_Y, NET_Y], color='#ffffff', linewidth=3.0, zorder=10)
ax.text(6.0, NET_Y, 'NET', color='#ffffff', verticalalignment='center', fontsize=9, fontweight='bold')

# 各ライン
ax.plot([-4.115, 4.115], [5.485, 5.485], color='#94a3b8', linewidth=1.5)
ax.plot([-4.115, 4.115], [18.285, 18.285], color='#94a3b8', linewidth=1.5)
ax.plot([0, 0], [5.485, 18.285], color='#94a3b8', linewidth=1.5)
ax.plot([0, 0], [0, 0.4], color='#cbd5e1', linewidth=1.5)
ax.plot([0, 0], [23.37, 23.77], color='#cbd5e1', linewidth=1.5)

color_focal = '#38bdf8'     # 手前: 水色
color_opp = '#fb923c'       # 相手: オレンジ
color_net_miss = '#ef4444'  # ネットミス: 赤

for i, cur in enumerate(records):
    c = color_focal if cur['player'] == target_player else color_opp
    is_net = (cur['result'] == 'NET')
    target_x, target_y = cur['bx'], cur['by']
    annotation_c = c
    
    # ネットミス延長処理
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
                        color=annotation_c, lw=2.2, alpha=0.95, linestyle=ls_arrow)
    )
    
    # 打点マーク
    if cur['shot'] == 1:
        ax.plot(cur['hx'], cur['hy'], marker='o', markersize=13, color='#eab308', markeredgecolor='#ffffff', markeredgewidth=2, zorder=5)
        ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, zorder=6)
        ax.text(cur['hx'], cur['hy'] - 0.7 if cur['hy'] < NET_Y else cur['hy'] + 0.7,
                '★SERVE', color='#fde047', fontsize=8, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#000000', edgecolor='#fde047', alpha=0.85))
    else:
        ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, markeredgecolor='#ffffff', markeredgewidth=1, zorder=4)
        
    # バウンドマーク / ネットマーク
    if is_net:
        ax.plot(target_x, target_y, marker='X', markersize=16, color=color_net_miss, markeredgecolor='#ffffff', markeredgewidth=2, zorder=11)
    else:
        b_marker = '*' if cur['result'] == 'IN' else 'x'
        ax.plot(target_x, target_y, marker=b_marker, markersize=11, color=annotation_c, markeredgecolor='#ffffff', markeredgewidth=1.5, zorder=4)
        
    # バウンドから次の打点への点線
    if i + 1 < len(records) and not is_net:
        nxt = records[i+1]
        ax.annotate(
            '', xy=(nxt['hx'], nxt['hy']), xytext=(cur['bx'], cur['by']),
            arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.4",
                            color=c, lw=1.5, alpha=0.6, linestyle=':')
        )
        
    # ショットラベル
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

# 手前・奥ラベル
ax.text(0, -2.0, f"NEAR: {target_player}", color='#38bdf8', fontsize=12, fontweight='bold', ha='center')
ax.text(0, 25.2, "FAR: OPPONENT", color='#fb923c', fontsize=12, fontweight='bold', ha='center')

ax.set_xlim(-6.8, 6.8)
ax.set_ylim(-3.5, 27.2)
ax.set_aspect('equal', adjustable='box')
ax.axis('off')

# コートを中央寄せで表示
st.pyplot(fig, use_container_width=False)

# ----------------------------------------------------
# 【メイン画面】コートの下に概要 ＆ ショット詳細を表示
# ----------------------------------------------------
st.markdown("---")
st.subheader(f"📌 Point {selected_point} 概要")
st.metric(label="ポイント勝敗", value=p_info['Point_Outcome'])
st.write(f"**ラリー打数:** {p_info['Total_Shots']} 打 ｜ **決まり方:** {p_info['Finish_Type']}")
st.write(f"**決着展開:** {p_info['Detail']}")
if p_info['Key_Category'] != 'なし':
    st.write(f"**手前のキーショット:** {p_info['Key_Category']} ({p_info['Key_Type']} / {p_info['Key_Course']})")

st.write("##### ショット詳細")
display_df = p_shots.copy()
display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
display_df['Result'] = display_df['Result'].apply(translate_result)

cols_to_show = ['Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)
