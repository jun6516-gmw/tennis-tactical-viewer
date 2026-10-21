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

# ポイントサマリー & 手前選手のキーショット特定（元の安定した状態に戻しています）
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
    return pd.DataFrame(points_data)

full_meta_df = analyze_points_and_keyshots(shots_df, target_player)

# ----------------------------------------------------
# サイドバー: 段階連動型フィルタUI
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
c_srv_wde = len(df_srv
