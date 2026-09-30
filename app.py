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

# ページ基本設定
st.set_page_config(page_title="Tennis Match Tactical Visualizer", layout="wide")
st.title("🎾 テニス戦術分析ダッシュボード")
st.caption("SwingVisionのデータから、1ポイントごとのボール軌跡・得失点文脈を可視化します")

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

# ポイントサマリー作成
@st.cache_data
def analyze_points(df, focus_player):
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
            
        points_data.append({
            'Point': int(point_id),
            'Total_Shots': total_shots,
            'Point_Outcome': point_outcome,
            'Finish_Type': finish_type,
            'Last_Player': last_player,
            'Last_Stroke': last_stroke,
            'Last_Result': last_res,
            'Detail': f"{last_player}: {last_stroke} -> {last_res}"
        })
    return pd.DataFrame(points_data)

points_summary_df = analyze_points(shots_df, target_player)

# ショット特徴量の集計
@st.cache_data
def extract_shot_features(df):
    features = {}
    grouped = df.groupby('Point')
    
    for pt, grp in grouped:
        pt = int(pt)
        feats = {
            'has_serve_center': False,
            'has_serve_wide': False,
            'has_stroke_fore': False,
            'has_stroke_back': False,
            'has_stroke_cross': False,
            'has_stroke_inside': False,
            'has_volley_fore': False,
            'has_volley_back': False,
            'has_volley_cross': False,
            'has_volley_inside': False,
            'has_smash_cross': False,
            'has_smash_inside': False,
        }
        
        for _, row in grp.iterrows():
            stk = str(row.get('Stroke', ''))
            dir_val = str(row.get('Direction', ''))
            
            # サーブ
            if 'サーブ' in stk or 'Serve' in stk:
                if 'センター' in dir_val or 'Center' in dir_val or 'T' in dir_val:
                    feats['has_serve_center'] = True
                if 'ワイド' in dir_val or 'Wide' in dir_val:
                    feats['has_serve_wide'] = True
            
            # グラウンドストローク
            is_stroke = ('フォアハンド' in stk or 'バックハンド' in stk or 'Forehand' in stk or 'Backhand' in stk) and ('ボレー' not in stk and 'Volley' not in stk and 'スマッシュ' not in stk and 'Smash' not in stk)
            if is_stroke:
                if 'フォア' in stk or 'Forehand' in stk:
                    feats['has_stroke_fore'] = True
                if 'バック' in stk or 'Backhand' in stk:
                    feats['has_stroke_back'] = True
                if 'クロス' in dir_val or 'Cross' in dir_val:
                    feats['has_stroke_cross'] = True
                if '逆クロス' in dir_val or 'Inside-Out' in dir_val or 'ストレート' in dir_val or 'Down the Line' in dir_val:
                    feats['has_stroke_inside'] = True

            # ボレー
            if 'ボレー' in stk or 'Volley' in stk:
                if 'フォア' in stk or 'Forehand' in stk:
                    feats['has_volley_fore'] = True
                if 'バック' in stk or 'Backhand' in stk:
                    feats['has_volley_back'] = True
                if 'クロス' in dir_val or 'Cross' in dir_val:
                    feats['has_volley_cross'] = True
                if '逆クロス' in dir_val or 'Inside-Out' in dir_val or 'ストレート' in dir_val or 'Down the Line' in dir_val:
                    feats['has_volley_inside'] = True

            # スマッシュ
            if 'スマッシュ' in stk or 'Smash' in stk:
                if 'クロス' in dir_val or 'Cross' in dir_val:
                    feats['has_smash_cross'] = True
                if '逆クロス' in dir_val or 'Inside-Out' in dir_val or 'ストレート' in dir_val or 'Down the Line' in dir_val:
                    feats['has_smash_inside'] = True

        features[pt] = feats
    return pd.DataFrame.from_dict(features, orient='index').reset_index().rename(columns={'index': 'Point'})

shot_features_df = extract_shot_features(shots_df)
full_meta_df = pd.merge(points_summary_df, shot_features_df, on='Point', how='left')

# ----------------------------------------------------
# サイドバー: 連動型フィルタUI（母集団連動カウント）
# ----------------------------------------------------
st.sidebar.header("🔍 フィルタ設定")

# 1. ポイント（取った／落とした／すべて）
c_all = len(full_meta_df)
c_won = len(full_meta_df[full_meta_df['Point_Outcome'] == '取った'])
c_lost = len(full_meta_df[full_meta_df['Point_Outcome'] == '落とした'])

opt_point_list = ["すべて", "取った", "落とした"]
def format_point(opt):
    if opt == "すべて": return f"すべて ({c_all})"
    if opt == "取った": return f"取った ({c_won})"
    if opt == "落とした": return f"落とした ({c_lost})"
    return opt

sel_point = st.sidebar.selectbox("■ ポイント", opt_point_list, format_func=format_point, key="f_point")

# ポイント選択に基づいた現在の母集団 (Base DF)
if sel_point == "すべて":
    base_df = full_meta_df
else:
    base_df = full_meta_df[full_meta_df['Point_Outcome'] == sel_point]

base_count = len(base_df)

# 2. 決まり方（エース／アウト／ネット／すべて） - base_dfに連動
c_ace = len(base_df[base_df['Finish_Type'] == 'エース'])
c_out = len(base_df[base_df['Finish_Type'] == 'アウト'])
c_net = len(base_df[base_df['Finish_Type'] == 'ネット'])

opt_finish_list = ["すべて", "エース", "アウト", "ネット"]
def format_finish(opt):
    if opt == "すべて": return f"すべて ({base_count})"
    if opt == "エース": return f"エース ({c_ace})"
    if opt == "アウト": return f"アウト ({c_out})"
    if opt == "ネット": return f"ネット ({c_net})"
    return opt

sel_finish = st.sidebar.selectbox("■ 決まり方", opt_finish_list, format_func=format_finish, key="f_finish")

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🎾 ショットフィルタ")

# サービス - base_dfに連動
c_srv_cen = len(base_df[base_df['has_serve_center'] == True])
c_srv_wde = len(base_df[base_df['has_serve_wide'] == True])

opt_srv_list = ["すべて", "センター", "ワイド"]
def format_srv(opt):
    if opt == "すべて": return f"すべて ({base_count})"
    if opt == "センター": return f"センター ({c_srv_cen})"
    if opt == "ワイド": return f"ワイド ({c_srv_wde})"
    return opt

sel_serve = st.sidebar.selectbox("サービス コース", opt_srv_list, format_func=format_srv, key="f_serve")

# グラウンドストローク - base_dfに連動
c_strk_fh = len(base_df[base_df['has_stroke_fore'] == True])
c_strk_bh = len(base_df[base_df['has_stroke_back'] == True])
c_strk_cr = len(base_df[base_df['has_stroke_cross'] == True])
c_strk_in = len(base_df[base_df['has_stroke_inside'] == True])

col_gs1, col_gs2 = st.sidebar.columns(2)
with col_gs1:
    opt_gs_type_list = ["すべて", "フォア", "バック"]
    def format_gs_t(opt):
        if opt == "すべて": return f"すべて ({base_count})"
        if opt == "フォア": return f"フォア ({c_strk_fh})"
        if opt == "バック": return f"バック ({c_strk_bh})"
        return opt
    sel_gs_type = st.selectbox("ストローク タイプ", opt_gs_type_list, format_func=format_gs_t, key="f_gs_type")

with col_gs2:
    opt_gs_course_list = ["すべて", "クロス", "逆クロス"]
    def format_gs_c(opt):
        if opt == "すべて": return f"すべて ({base_count})"
        if opt == "クロス": return f"クロス ({c_strk_cr})"
        if opt == "逆クロス": return f"逆クロス ({c_strk_in})"
        return opt
    sel_gs_course = st.selectbox("ストローク コース", opt_gs_course_list, format_func=format_gs_c, key="f_gs_course")

# ボレー - base_dfに連動
c_vol_fh = len(base_df[base_df['has_volley_fore'] == True])
c_vol_bh = len(base_df[base_df['has_volley_back'] == True])
c_vol_cr = len(base_df[base_df['has_volley_cross'] == True])
c_vol_in = len(base_df[base_df['has_volley_inside'] == True])

col_vol1, col_vol2 = st.sidebar.columns(2)
with col_vol1:
    opt_vol_type_list = ["すべて", "フォア", "バック"]
    def format_vol_t(opt):
        if opt == "すべて": return f"すべて ({base_count})"
        if opt == "フォア": return f"フォア ({c_vol_fh})"
        if opt == "バック": return f"バック ({c_vol_bh})"
        return opt
    sel_vol_type = st.selectbox("ボレー タイプ", opt_vol_type_list, format_func=format_vol_t, key="f_vol_type")

with col_vol2:
    opt_vol_course_list = ["すべて", "クロス", "逆クロス"]
    def format_vol_c(opt):
        if opt == "すべて": return f"すべて ({base_count})"
        if opt == "クロス": return f"クロス ({c_vol_cr})"
        if opt == "逆クロス": return f"逆クロス ({c_vol_in})"
        return opt
    sel_vol_course = st.selectbox("ボレー コース", opt_vol_course_list, format_func=format_vol_c, key="f_vol_course")

# スマッシュ - base_dfに連動
c_sm_cr = len(base_df[base_df['has_smash_cross'] == True])
c_sm_in = len(base_df[base_df['has_smash_inside'] == True])

opt_smash_list = ["すべて", "クロス", "逆クロス"]
def format_smash(opt):
    if opt == "すべて": return f"すべて ({base_count})"
    if opt == "クロス": return f"クロス ({c_sm_cr})"
    if opt == "逆クロス": return f"逆クロス ({c_sm_in})"
    return opt
sel_smash = st.sidebar.selectbox("スマッシュ コース", opt_smash_list, format_func=format_smash, key="f_smash")

# ----------------------------------------------------
# 最終フィルタ適用処理
# ----------------------------------------------------
cond = pd.Series(True, index=base_df.index)

if sel_finish != "すべて":
    cond &= (base_df['Finish_Type'] == sel_finish)

if sel_serve == "センター":
    cond &= (base_df['has_serve_center'] == True)
elif sel_serve == "ワイド":
    cond &= (base_df['has_serve_wide'] == True)

if sel_gs_type == "フォア":
    cond &= (base_df['has_stroke_fore'] == True)
elif sel_gs_type == "バック":
    cond &= (base_df['has_stroke_back'] == True)

if sel_gs_course == "クロス":
    cond &= (base_df['has_stroke_cross'] == True)
elif sel_gs_course == "逆クロス":
    cond &= (base_df['has_stroke_inside'] == True)

if sel_vol_type == "フォア":
    cond &= (base_df['has_volley_fore'] == True)
elif sel_vol_type == "バック":
    cond &= (base_df['has_volley_back'] == True)

if sel_vol_course == "クロス":
    cond &= (base_df['has_volley_cross'] == True)
elif sel_vol_course == "逆クロス":
    cond &= (base_df['has_volley_inside'] == True)

if sel_smash == "クロス":
    cond &= (base_df['has_smash_cross'] == True)
elif sel_smash == "逆クロス":
    cond &= (base_df['has_smash_inside'] == True)

filtered_points = base_df[cond]

if filtered_points.empty:
    st.warning("⚠️ 選択した条件に一致するポイントがありません。フィルタ条件を緩和してください。")
    st.stop()

point_list = filtered_points['Point'].tolist()

# ----------------------------------------------------
# ポイント選択 & ナビゲーション
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header(f"🎯 ポイント選択 (該当: {len(point_list)} 件)")

if "current_point_idx" not in st.session_state:
    st.session_state.current_point_idx = 0

if st.session_state.current_point_idx >= len(point_list):
    st.session_state.current_point_idx = 0

def on_selectbox_change():
    chosen_pt = st.session_state.sb_point
    st.session_state.current_point_idx = point_list.index(chosen_pt)

selected_point_sb = st.sidebar.selectbox(
    "Select Point #",
    options=point_list,
    index=st.session_state.current_point_idx,
    key="sb_point",
    on_change=on_selectbox_change
)

col_prev, col_next = st.sidebar.columns(2)
with col_prev:
    if st.button("◀ 前へ", use_container_width=True):
        if st.session_state.current_point_idx > 0:
            st.session_state.current_point_idx -= 1
            st.rerun()

with col_next:
    if st.button("次へ ▶", use_container_width=True):
        if st.session_state.current_point_idx < len(point_list) - 1:
            st.session_state.current_point_idx += 1
            st.rerun()

st.sidebar.markdown(
    """
    <div id="wheel-box" style="
        border: 2px dashed #0284c7;
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        background-color: #0f172a;
        cursor: ns-resize;
        margin-top: 6px;
        user-select: none;
    ">
        <span style="font-size: 12px; color: #38bdf8; font-weight: bold;">
            🖱️ マウスホイール操作エリア
        </span><br>
        <span style="font-size: 10px; color: #94a3b8;">
            この枠上でホイールを回すと前後に移動します
        </span>
    </div>

    <script>
    const box = window.parent.document.getElementById('wheel-box');
    if (box && !box.hasAttribute('listener-attached')) {
        box.setAttribute('listener-attached', 'true');
        box.addEventListener('wheel', function(e) {
            e.preventDefault();
            const buttons = window.parent.document.querySelectorAll('button');
            let prevBtn = null;
            let nextBtn = null;
            buttons.forEach(b => {
                if (b.innerText.includes('前へ')) prevBtn = b;
                if (b.innerText.includes('次へ')) nextBtn = b;
            });
            if (e.deltaY > 0 && nextBtn) {
                nextBtn.click();
            } else if (e.deltaY < 0 && prevBtn) {
                prevBtn.click();
            }
        }, { passive: false });
    }
    </script>
    """,
    unsafe_allow_html=True
)

selected_point = point_list[st.session_state.current_point_idx]
st.sidebar.caption(f"位置: **{st.session_state.current_point_idx + 1} / {len(point_list)}** (Point #{selected_point})")

st.sidebar.header("🎨 表示モード")
view_mode = st.sidebar.radio(
    "描画モード",
    ["全ラリー表示", "決着ラスト2打のみ表示"],
    index=0
)

# ----------------------------------------------------
# メイン画面描画
# ----------------------------------------------------
p_shots = shots_df[shots_df['Point'] == selected_point].sort_values('Shot').copy()
p_info = points_summary_df[points_summary_df['Point'] == selected_point].iloc[0]

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader(f"📌 Point {selected_point} 概要")
    st.metric(label="ポイント勝敗", value=p_info['Point_Outcome'])
    st.write(f"**ラリー打数:** {p_info['Total_Shots']} 打")
    st.write(f"**決まり方:** {p_info['Finish_Type']}")
    st.write(f"**決着展開:** {p_info['Detail']}")
    
    st.write("---")
    st.write("##### ショット詳細")
    
    display_df = p_shots.copy()
    display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
    display_df['Result'] = display_df['Result'].apply(translate_result)
    
    cols_to_show = ['Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
    st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)

with col2:
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
        
    fig, ax = plt.subplots(figsize=(7, 12), facecolor='#0f172a')
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

    ax.set_xlim(-6.5, 6.5)
    ax.set_ylim(-3.5, 27)
    ax.set_aspect('equal')
    ax.axis('off')
    
    st.pyplot(fig)
