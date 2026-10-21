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
    /* 1. デフォルト（サイドバーが折りたたまれている時・スマホ表示時） */
    .msg-pc {
        display: none !important;
    }
    .msg-sp {
        display: inline !important;
    }
    
    /* 2. サイドバーが開いて展開されている時（aria-expanded="true"）のみ「左側の〜」を表示 */
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .msg-pc {
        display: inline !important;
    }
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .msg-sp {
        display: none !important;
    }
    </style>
    
    <div style="background-color: #f0f7ff; color: #1e3a8a; padding: 14px 16px; border-radius: 8px; border-left: 5px solid #2563eb; margin: 10px 0;">
        <span class="msg-pc">👈 <strong>左側のサイドバーから</strong></span>
        <span class="msg-sp">👆 <strong>上の ＞＞ をクリックして</strong></span>
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
# サイドバー: マッチルール設定
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("⚙️ マッチルール設定")
match_rule = st.sidebar.selectbox(
    "マッチルール形式",
    ["通常（3セットとも6オール7pt TB）", "ファイナル10ptスーパーTB（1セットオール時）"],
    index=0
)
is_super_tb = (match_rule == "ファイナル10ptスーパーTB（1セットオール時）")

# ポイントサマリー & スコア計算 & キーショット特定
@st.cache_data
def analyze_points_and_keyshots(df, focus_player, is_super_tb_mode=False):
    points_data = []
    point_ids = sorted(df['Point'].unique())

    p_sets, o_sets = 0, 0
    p_games, o_games = 0, 0
    p_pts, o_pts = 0, 0
    past_sets = []

    pt_labels = ["0", "15", "30", "40"]

    for point_id in point_ids:
        group = df[df['Point'] == point_id]
        group_sorted = group.sort_values('Shot')
        last_shot = group_sorted.iloc[-1]

        last_player = str(last_shot['Player'])
        last_stroke = translate_stroke(last_shot['Stroke'])
        last_res = translate_result(last_shot['Result'])
        total_shots = len(group_sorted)

        # 勝敗判定
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

        # スコア状態判定
        current_set_num = p_sets + o_sets + 1
        is_final_super_tb = is_super_tb_mode and (p_sets == 1 and o_sets == 1)
        is_normal_tb = (not is_final_super_tb) and (p_games == 6 and o_games == 6)

        if is_final_super_tb or is_normal_tb:
            pt_score_str = f"TB {p_pts}-{o_pts}"
        else:
            if p_pts >= 3 and o_pts >= 3:
                if p_pts == o_pts:
                    pt_score_str = "40-40 (Deuce)"
                elif p_pts == o_pts + 1:
                    pt_score_str = "Ad-40"
                elif o_pts == p_pts + 1:
                    pt_score_str = "40-Ad"
                else:
                    pt_score_str = "40-40"
            else:
                pl = pt_labels[p_pts] if p_pts < 4 else "40"
                ol = pt_labels[o_pts] if o_pts < 4 else "40"
                pt_score_str = f"{pl}-{ol}"

        past_sets_str = " ".join([f"{ps}-{os}" for ps, os in past_sets])
        if is_final_super_tb:
            score_disp = f"Set {current_set_num} [Match TB]: {pt_score_str}"
        else:
            score_disp = f"Set {current_set_num} ({p_games}-{o_games}) {pt_score_str}"

        full_score_summary = f"{past_sets_str + ' ' if past_sets_str else ''}{score_disp}".strip()

        # 次ポイントへの更新
        if point_outcome == "取った":
            p_pts += 1
        else:
            o_pts += 1

        if is_final_super_tb:
            if p_pts >= 10 and p_pts >= o_pts + 2:
                p_sets += 1
                past_sets.append((f"[{p_pts}", f"{o_pts}]"))
                p_pts, o_pts = 0, 0
            elif o_pts >= 10 and o_pts >= p_pts + 2:
                o_sets += 1
                past_sets.append((f"[{p_pts}", f"{o_pts}]"))
                p_pts, o_pts = 0, 0
        elif is_normal_tb:
            if p_pts >= 7 and p_pts >= o_pts + 2:
                p_games += 1
                p_sets += 1
                past_sets.append((p_games, o_games))
                p_games, o_games, p_pts, o_pts = 0, 0, 0, 0
            elif o_pts >= 7 and o_pts >= p_pts + 2:
                o_games += 1
                o_sets += 1
                past_sets.append((p_games, o_games))
                p_games, o_games, p_pts, o_pts = 0, 0, 0, 0
        else:
            game_won = None
            if p_pts >= 4 and p_pts >= o_pts + 2:
                p_games += 1
                game_won = True
                p_pts, o_pts = 0, 0
            elif o_pts >= 4 and o_pts >= p_pts + 2:
                o_games += 1
                game_won = False
                p_pts, o_pts = 0, 0

            if game_won is not None:
                if (p_games >= 6 and p_games >= o_games + 2) or p_games == 7:
                    p_sets += 1
                    past_sets.append((p_games, o_games))
                    p_games, o_games = 0, 0
                elif (o_games >= 6 and o_games >= p_games + 2) or o_games == 7:
                    o_sets += 1
                    past_sets.append((p_games, o_games))
                    p_games, o_games = 0, 0

        # キーショット判定
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
            'Display_Score': full_score_summary,
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

full_meta_df = analyze_points_and_keyshots(shots_df, target_player, is_super_tb)

# ----------------------------------------------------
# サイドバー: 段階連動型フィルタUI
# ----------------------------------------------------
st.sidebar.markdown("---")
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

# 最終絞り込み
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

filter_signature = f"{sel_point}_{sel_finish}_{sel_serve}_{sel_gs_type}_{sel_gs_course}_{sel_vol_type}_{sel_vol_course}_{sel_smash}_{match_rule}"
if "last_filter_signature" not in st.session_state or st.session_state.last_filter_signature != filter_signature:
    st.session_state.last_filter_signature = filter_signature
    st.session_state.current_point_idx = 0

if "current_point_idx" not in st.session_state or st.session_state.current_point_idx >= len(point_list):
    st.session_state.current_point_idx = 0

st.sidebar.markdown("---")
st.sidebar.header("🎨 表示設定")
view_mode = st.sidebar.radio(
    "描画モード",
    ["全ラリー表示", "決着ラスト2打のみ表示"],
    index=0
)

# ----------------------------------------------------
# ナビゲーション管理
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
/* ページ最上部の余白 */
.block-container {
    padding-top: 3.2rem !important;
    padding-bottom: 1rem !important;
}

/* 要素同士の縦方向の隙間を適度に調整 */
[data-testid="stVerticalBlock"] {
    gap: 0.4rem !important;
}

/* ナビボタン(◀ ▶)の高さとフォント */
div[data-testid="stColumn"] button {
    height: 38px !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: bold !important;
}

/* スマホ時（幅768px以下）のみコート図を70%に縮小して中央寄せ */
@media (max-width: 768px) {
    div.element-container:has(figure) {
        width: 70% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 現在選択されているポイントのデータを抽出
selected_point = point_list[st.session_state.current_point_idx]
p_shots = shots_df[shots_df['Point'] == selected_point].sort_values('Shot').copy()
p_info = full_meta_df[full_meta_df['Point'] == selected_point].iloc[0]

# 1段目: ナビゲーション（◀, Point#, ▶ をコンパクトに中央寄せ・左寄せ配置）
col_prev, col_sel, col_next, _ = st.columns([1, 2, 1, 6])

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

# 2段目: スコア表示（ボタンの真下にすっきり1行で配置、コート図と完全に独立）
score_text = p_info['Display_Score']
outcome_badge = "🟢" if p_info['Point_Outcome'] == "取った" else "🔴"

st.markdown(f"""
<div style="font-size: 11px; color: #94a3b8; font-family: monospace; letter-spacing: 0.3px; padding: 2px 0 4px 2px; margin: 0;">
    <span style="color: #f8fafc; font-weight: bold;">{score_text}</span> ｜ {outcome_badge}
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 左右2分割（PC：左コート・右詳細 / スマホ：上コート・下詳細）
# ----------------------------------------------------
col_court, col_info = st.columns([1.1, 1.0])

# ====================================================
# 【コート描画】
# ====================================================
with col_court:
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
# 【概要 ＆ ショット詳細】
# ====================================================
with col_info:
    st.subheader(f"📌 Point {selected_point}")
    st.metric(label="ポイント勝敗", value=p_info['Point_Outcome'])
    st.write(f"**ラリー打数:** {p_info['Total_Shots']} 打 ｜ **決まり方:** {p_info['Finish_Type']}")
    st.write(f"**決着展開:** {p_info['Detail']}")
    if p_info['Key_Category'] != 'なし':
        st.write(f"**手前のキーショット:** {p_info['Key_Category']} ({p_info['Key_Type']} / {p_info['Key_Course']})")

    st.write("---")
    st.write("##### ショット詳細")
    display_df = p_shots.copy()
    display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
    display_df['Result'] = display_df['Result'].apply(translate_result)

    cols_to_show = ['Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
    st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)
