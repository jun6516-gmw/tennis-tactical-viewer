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

# ----------------------------------------------------
# テニススコア（ゲーム・ポイント）の算出関数
# ----------------------------------------------------
POINT_STR_MAP = {0: "0", 1: "15", 2: "30", 3: "40"}

def compute_point_scores(points_summary):
    """ポイントごとの手前側目線のスコアを計算してリストで返す"""
    scores = []
    games_won = 0
    games_lost = 0
    pts_won = 0
    pts_lost = 0

    for item in points_summary:
        won = (item['Point_Outcome'] == "取った")

        # 現在のゲーム内ポイント文字列
        if pts_won >= 3 and pts_lost >= 3:
            if pts_won == pts_lost:
                pt_disp = "40-40 (Deuce)"
            elif pts_won == pts_lost + 1:
                pt_disp = "Ad-40"
            else:
                pt_disp = "40-Ad"
        else:
            pt_disp = f"{POINT_STR_MAP.get(pts_won, '40')}-{POINT_STR_MAP.get(pts_lost, '40')}"

        game_disp = f"{games_won}-{games_lost}"
        scores.append(f"Game {game_disp} ({pt_disp})")

        # ポイント加算・ゲームカウント更新
        if won:
            pts_won += 1
        else:
            pts_lost += 1

        # ゲーム決着判定
        if pts_won >= 4 and pts_won - pts_lost >= 2:
            games_won += 1
            pts_won, pts_lost = 0, 0
        elif pts_lost >= 4 and pts_lost - pts_won >= 2:
            games_lost += 1
            pts_won, pts_lost = 0, 0

    return scores

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
        else:
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
    
    # スコア計算結果を付与
    scores = compute_point_scores(points_data)
    for idx, sc in enumerate(scores):
        points_data[idx]['Score'] = sc

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
# 【メイン画面】ナビゲーション
# ----------------------------------------------------
if "main_pt_select" not in st.session_state or st.session_state.main_pt_select not in point_list:
    st.session_state.main_pt_select = point_list[st.session_state.current_point_idx]

def go_prev_pt():
    if st.session_state.current_point_idx > 0:
        st.session_state.current_point_idx -= 1
        st.session_state.main_pt_select = point_list[st.session_state.current_point_idx]

def go_next_pt():
    if st.session_state.current_point_idx < len(point_list) - 1:
        st.session_state.current_point_idx += 1
        st.session_state.main_pt_select = point_list[st.session_state.current_point_idx]

def on_main_select():
    chosen = st.session_state.main_pt_select
    if chosen in point_list:
        st.session_state.current_point_idx = point_list.index(chosen)

# ----------------------------------------------------
# ナビゲーション & スマホ用コート図縮小CSS
# ----------------------------------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 1rem !important;
}

[data-testid="stVerticalBlock"] {
    gap: 0.3rem !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: flex-start !important;
    align-items: center !important;
    gap: 6px !important;
    width: 100% !important;
    margin-top: 0px !important;
    margin-bottom: -12px !important;
    padding-bottom: 0px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-testid="stColumn"],
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-testid="column"] {
    min-width: 0 !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="stColumn"]:first-child,
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="stColumn"]:last-child,
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="column"]:first-child,
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="column"]:last-child {
    flex: 0 0 48px !important;
    width: 48px !important;
    max-width: 48px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="stColumn"]:nth-child(2),
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="column"]:nth-child(2) {
    flex: 0 0 90px !important;
    width: 90px !important;
    max-width: 90px !important;
}

[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) button {
    height: 40px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

[data-testid="stImage"], [data-testid="stPlotlyChart"], div.element-container:has(figure) {
    margin-top: 0px !important;
    padding-top: 0px !important;
}

@media (max-width: 768px) {
    [data-testid="stPlotlyChart"],
    div.element-container:has(figure),
    [data-testid="stImage"] {
        width: 70% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 3カラム配置
col_prev, col_sel, col_next = st.columns([1, 6, 1])

with col_prev:
    st.button("◀", key="main_prev", on_click=go_prev_pt, use_container_width=True)

with col_sel:
    st.selectbox(
        "Point #",
        options=point_list,
        key="main_pt_select",
        on_change=on_main_select,
        label_visibility="collapsed"
    )

with col_next:
    st.button("▶", key="main_next", on_click=go_next_pt, use_container_width=True)

selected_point = point_list[st.session_state.current_point_idx]
p_shots = shots_df[shots_df['Point'] == selected_point].sort_values('Shot').copy()
p_info = full_meta_df[full_meta_df['Point'] == selected_point].iloc[0]

# 左右2分割（PC：左コート・右詳細 / スマホ：上コート・下詳細）
col_court, col_info = st.columns([1.1, 1.0])

# ====================================================
# 【左側 / 上側】コート描画
# ====================================================
with col_court:
    NET_Y = 11.885
    focal_shots = p_shots[p_shots['Player'] == target_player]
